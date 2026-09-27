#!/usr/bin/env python3
"""财政补贴名单导入平台 - 应用入口与路由。"""
import csv
import io
import os
import sys
import urllib.parse
from wsgiref.simple_server import make_server

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from subsidy import db, services, views
from subsidy.web import (Response, route, redirect, not_found, application,
                         make_session_cookie, parse_session)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- 会话与权限

def current_user(req):
    morsel = req.cookies.get("sid")
    if not morsel:
        return None
    uid = parse_session(morsel.value)
    if uid is None:
        return None
    return db.get_user(uid)


def require_user(req):
    """返回 (user, None) 或 (None, 重定向响应)。"""
    user = current_user(req)
    if not user:
        return None, redirect("/login")
    return user, None


def _with_cookie(resp, name, value, max_age=None):
    cookie = "%s=%s; HttpOnly; Path=/; SameSite=Lax" % (name, value)
    if max_age is not None:
        cookie += "; Max-Age=%d" % max_age
    resp.headers.append(("Set-Cookie", cookie))
    return resp


# ---------------------------------------------------------------- 登录 / 退出

@route("GET", "/login")
def login_get(req):
    if current_user(req):
        return redirect("/")
    return Response(views.login_page(req.query.get("err", "")))


@route("POST", "/login")
def login_post(req):
    username = req.form.get("username", "").strip()
    password = req.form.get("password", "")
    user = db.verify_user(username, password)
    if not user:
        return Response(views.login_page("账号或密码错误"))
    resp = redirect("/")
    return _with_cookie(resp, "sid", make_session_cookie(user["id"]))


@route("GET", "/logout")
def logout(req):
    resp = redirect("/login")
    return _with_cookie(resp, "sid", "", max_age=0)


# ---------------------------------------------------------------- 任务列表

@route("GET", "/")
def index(req):
    user, resp = require_user(req)
    if not user:
        return resp
    tasks = services.list_tasks(user)
    return Response(views.task_list_page(user, tasks, req.query.get("msg", "")))


# ---------------------------------------------------------------- 导入

@route("GET", "/upload")
def upload_get(req):
    user, resp = require_user(req)
    if not user:
        return resp
    if user["role"] != "township":
        return redirect("/?msg=" + urllib.parse.quote("管理员账号仅用于监管查看，请使用乡镇账号导入"))
    return Response(views.upload_page(user))


@route("POST", "/upload")
def upload_post(req):
    user, resp = require_user(req)
    if not user:
        return resp
    if user["role"] != "township":
        return redirect("/?msg=" + urllib.parse.quote("管理员账号仅用于监管查看，请使用乡镇账号导入"))
    uploaded = req.files.get("file")
    if not uploaded:
        return Response(views.upload_page(user, "请选择要上传的 CSV 文件"))
    filename, content = uploaded
    if not filename.lower().endswith(".csv"):
        return Response(views.upload_page(user, "仅支持 CSV 文件（Excel 请另存为 CSV）"))
    if len(content) > services.MAX_FILE_BYTES:
        return Response(views.upload_page(user, "文件超过 5MB 限制"))
    try:
        task_id, summary = services.import_file(user, os.path.basename(filename), content)
    except services.ImportError_ as e:
        return Response(views.upload_page(user, str(e)))
    msg = "导入完成：共 %d 行，校验通过 %d 行，失败 %d 行" % (
        summary["total"], summary["valid"], summary["invalid"])
    return redirect("/tasks/%d?msg=%s" % (task_id, urllib.parse.quote(msg)))


# ---------------------------------------------------------------- 任务详情 / 上送 / 错误清单

@route("GET", "/tasks/<int:tid>")
def task_detail(req, tid):
    user, resp = require_user(req)
    if not user:
        return resp
    task, records = services.list_records(user, tid)
    if task is None:
        return not_found("任务不存在或不属于当前乡镇")
    batches = services.list_batches(user, tid)
    return Response(views.task_detail_page(user, task, records, batches,
                                           req.query.get("msg", "")))


@route("POST", "/tasks/<int:tid>/submit")
def task_submit(req, tid):
    user, resp = require_user(req)
    if not user:
        return resp
    result = services.submit_task(user, tid)
    if result is None:
        return not_found("任务不存在或不属于当前乡镇")
    if result["batches"] == 0:
        msg = "没有待上送的有效记录"
    else:
        msg = "分批上送完成：共 %d 批，成功 %d 条，退回 %d 条" % (
            result["batches"], result["success"], result["failed"])
    return redirect("/tasks/%d?msg=%s" % (tid, urllib.parse.quote(msg)))


@route("GET", "/tasks/<int:tid>/errors")
def task_errors(req, tid):
    user, resp = require_user(req)
    if not user:
        return resp
    task, errors = services.list_errors(user, tid)
    if task is None:
        return not_found("任务不存在或不属于当前乡镇")
    return Response(views.error_list_page(user, task, errors))


@route("GET", "/tasks/<int:tid>/errors.csv")
def task_errors_csv(req, tid):
    user, resp = require_user(req)
    if not user:
        return resp
    task, errors = services.list_errors(user, tid)
    if task is None:
        return not_found("任务不存在或不属于当前乡镇")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["任务编号", "行号", "补贴对象", "身份证号", "银行卡号",
                "金额(元)", "乡镇", "批次", "退回原因"])
    for r in errors:
        w.writerow([task["task_no"], r["row_no"], r["name"], r["id_card"], r["bank_card"],
                    "%.2f" % (r["amount_cents"] / 100), r["township"],
                    r["batch_no"] or "", r["submit_message"]])
    data = b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")  # BOM 便于 Excel 打开
    fname = urllib.parse.quote("错误清单_%s.csv" % task["task_no"])
    return Response(data, content_type="text/csv; charset=utf-8",
                    headers=[("Content-Disposition",
                              "attachment; filename*=UTF-8''%s" % fname)])


# ---------------------------------------------------------------- 模板下载

@route("GET", "/sample.csv")
def sample_csv(req):
    user, resp = require_user(req)
    if not user:
        return resp
    path = os.path.join(BASE_DIR, "template.csv")
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
    else:
        data = "补贴对象,身份证号,银行卡号,金额,乡镇\n".encode("utf-8-sig")
    return Response(data, content_type="text/csv; charset=utf-8",
                    headers=[("Content-Disposition", "attachment; filename=template.csv")])


# ---------------------------------------------------------------- 启动

def main():
    db.init_db()
    port = int(os.environ.get("PORT", "8000"))
    print("财政补贴名单导入平台已启动: http://127.0.0.1:%d" % port)
    print("初始账号见 README.md（如 chengdong / Town@2026）")
    with make_server("0.0.0.0", port, application) as srv:
        srv.serve_forever()


if __name__ == "__main__":
    main()
