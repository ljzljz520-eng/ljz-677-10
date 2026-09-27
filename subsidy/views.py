"""页面 HTML 渲染。所有动态内容统一经 esc() 转义，防止 XSS。"""
from html import escape as esc


def fmt_money(cents):
    return "{:,}.{:02d}".format(cents // 100, cents % 100)


def mask_id(id_card):
    """身份证号脱敏：前6后4。"""
    if id_card and len(id_card) >= 10:
        return id_card[:6] + "*" * (len(id_card) - 10) + id_card[-4:]
    return id_card or ""


def mask_card(card):
    """银行卡号脱敏：仅后4位。"""
    if card and len(card) >= 4:
        return "**** **** " + card[-4:]
    return card or ""


CSS = """
* { box-sizing: border-box; }
body { margin:0; font-family:"Microsoft YaHei","PingFang SC",sans-serif; background:#f0f2f5; color:#333; }
.nav { background:#1f4e79; color:#fff; padding:0 24px; height:52px; display:flex; align-items:center; gap:20px; }
.nav .brand { font-size:17px; font-weight:bold; margin-right:auto; }
.nav .who { font-size:13px; color:#cfe3f5; }
.nav a { color:#fff; text-decoration:none; font-size:14px; }
.nav a:hover { text-decoration:underline; }
.container { max-width:1280px; margin:24px auto; padding:0 16px; }
.card { background:#fff; border-radius:6px; padding:20px 24px; margin-bottom:20px;
        box-shadow:0 1px 3px rgba(0,0,0,.08); }
h2 { margin:0 0 16px; font-size:18px; color:#1f4e79; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th, td { border:1px solid #e3e8ee; padding:7px 9px; text-align:left; }
th { background:#f5f8fb; color:#456; white-space:nowrap; }
tr:nth-child(even) td { background:#fafcfe; }
.ok { color:#1a7f37; } .bad { color:#c0392b; }
.badge { display:inline-block; padding:2px 10px; border-radius:10px; font-size:12px; }
.b-green { background:#e3f5e9; color:#1a7f37; }
.b-red { background:#fdecea; color:#c0392b; }
.b-blue { background:#e8f0fe; color:#1a56db; }
.b-gray { background:#eef0f2; color:#666; }
.btn { display:inline-block; background:#1f4e79; color:#fff; border:none; padding:8px 20px;
       border-radius:4px; font-size:14px; cursor:pointer; text-decoration:none; }
.btn:hover { background:#2a6299; }
.btn.warn { background:#c0392b; }
.msg { background:#e3f5e9; border:1px solid #a9dfbf; color:#1a7f37; padding:10px 14px;
       border-radius:4px; margin-bottom:16px; font-size:14px; }
.err { background:#fdecea; border:1px solid #f5b7b1; color:#c0392b; padding:10px 14px;
       border-radius:4px; margin-bottom:16px; font-size:14px; }
.summary { display:flex; gap:16px; flex-wrap:wrap; margin-bottom:4px; }
.summary .item { background:#f5f8fb; border:1px solid #e3e8ee; border-radius:6px;
                 padding:12px 22px; text-align:center; min-width:110px; }
.summary .num { font-size:24px; font-weight:bold; }
.summary .lbl { font-size:12px; color:#789; margin-top:4px; }
.login-box { max-width:380px; margin:100px auto; }
.login-box input { width:100%; padding:10px; margin:8px 0; border:1px solid #ccd;
                   border-radius:4px; font-size:14px; }
.login-box .btn { width:100%; margin-top:8px; }
.toolbar { display:flex; gap:12px; align-items:center; margin-bottom:16px; flex-wrap:wrap; }
.small { font-size:12px; color:#789; }
.mono { font-family:Consolas,monospace; }
"""


def layout(title, user, body):
    nav = ""
    if user:
        import_link = '<a href="/upload">导入名单</a>' if user["role"] == "township" else ""
        nav = (
            '<div class="nav"><span class="brand">财政补贴名单导入平台</span>'
            '<a href="/">任务列表</a>' + import_link +
            '<span style="margin-left:auto"></span>'
            '<span class="who">' + esc(user["display_name"]) + '（' + esc(user["township"]) + '）</span>'
            '<a href="/logout">退出</a></div>'
        )
    return ("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>" + esc(title) + " - 财政补贴名单导入平台</title>"
            "<style>" + CSS + "</style></head><body>" + nav +
            "<div class='container'>" + body + "</div></body></html>")


def login_page(error=""):
    err = '<div class="err">' + esc(error) + '</div>' if error else ""
    body = (
        '<div class="card login-box"><h2>用户登录</h2>' + err +
        '<form method="post" action="/login">'
        '<input name="username" placeholder="账号" required autofocus>'
        '<input name="password" type="password" placeholder="密码" required>'
        '<button class="btn" type="submit">登 录</button></form>'
        '<p class="small">乡镇经办人账号只能查看本乡镇的导入任务。</p></div>'
    )
    return layout("登录", None, body)


def _msg_html(msg):
    return '<div class="msg">' + esc(msg) + '</div>' if msg else ""


def task_list_page(user, tasks, msg=""):
    rows = []
    for t in tasks:
        if t["status"] == "DONE":
            status = '<span class="badge b-green">已上送</span>'
        else:
            status = '<span class="badge b-blue">待上送</span>'
        rows.append(
            "<tr><td class='mono'>" + esc(t["task_no"]) + "</td>"
            "<td>" + esc(t["filename"]) + "</td>"
            "<td>" + esc(t["township"]) + "</td>"
            "<td>" + esc(t["operator"]) + "</td>"
            "<td>" + str(t["total_rows"]) + "</td>"
            "<td class='ok'>" + str(t["valid_rows"]) + "</td>"
            "<td class='bad'>" + str(t["invalid_rows"]) + "</td>"
            "<td class='ok'>" + str(t["success_rows"]) + "</td>"
            "<td class='bad'>" + str(t["failed_rows"]) + "</td>"
            "<td>" + status + "</td>"
            "<td class='small'>" + esc(t["created_at"]) + "</td>"
            "<td><a href='/tasks/" + str(t["id"]) + "'>详情</a></td></tr>"
        )
    table = ("<table><tr><th>任务编号</th><th>文件名</th><th>乡镇</th><th>经办人</th>"
             "<th>总行数</th><th>有效</th><th>无效</th><th>上送成功</th><th>上送失败</th>"
             "<th>状态</th><th>导入时间</th><th>操作</th></tr>"
             + ("".join(rows) if rows else
                "<tr><td colspan='12' style='text-align:center;color:#999'>暂无导入任务</td></tr>")
             + "</table>")
    upload_btn = ('<a class="btn" href="/upload">＋ 导入补贴名单</a>'
                  if user["role"] == "township" else "")
    body = (_msg_html(msg) +
            '<div class="card"><div class="toolbar">' + upload_btn +
            '<span class="small">当前账号：' + esc(user["township"]) +
            '，仅显示本乡镇导入任务</span></div>' + table + '</div>')
    return layout("任务列表", user, body)


def upload_page(user, error=""):
    err = '<div class="err">' + esc(error) + '</div>' if error else ""
    body = (
        '<div class="card"><h2>导入补贴名单</h2>' + err +
        '<form method="post" action="/upload" enctype="multipart/form-data">'
        '<p>选择 CSV 文件（UTF-8 或 GBK 编码，≤5MB，≤5000行）：</p>'
        '<p><input type="file" name="file" accept=".csv" required></p>'
        '<button class="btn" type="submit">上传并校验</button> '
        '<a class="btn" style="background:#6b7c8d" href="/sample.csv">下载导入模板</a>'
        '</form>'
        '<p class="small">模板列：补贴对象、身份证号、银行卡号、金额、乡镇。'
        '系统将校验：身份证格式与校验码、银行卡号有效性、金额范围（0~50000元）、'
        '乡镇归属（须为 ' + esc(user["township"]) + '）、文件内及历史重复。</p></div>'
    )
    return layout("导入名单", user, body)


def task_detail_page(user, task, records, batches, msg=""):
    # 汇总
    ok_rows = sum(1 for r in records if r["check_status"] == "OK")
    err_rows = len(records) - ok_rows
    succ = sum(1 for r in records if r["submit_status"] == "SUCCESS")
    fail = sum(1 for r in records if r["submit_status"] == "FAILED")
    pending = sum(1 for r in records if r["check_status"] == "OK" and r["submit_status"] == "PENDING")
    summary = (
        '<div class="summary">'
        '<div class="item"><div class="num">' + str(task["total_rows"]) + '</div><div class="lbl">总行数</div></div>'
        '<div class="item"><div class="num ok">' + str(ok_rows) + '</div><div class="lbl">校验通过</div></div>'
        '<div class="item"><div class="num bad">' + str(err_rows) + '</div><div class="lbl">校验失败</div></div>'
        '<div class="item"><div class="num ok">' + str(succ) + '</div><div class="lbl">上送成功</div></div>'
        '<div class="item"><div class="num bad">' + str(fail) + '</div><div class="lbl">上送退回</div></div>'
        '<div class="item"><div class="num">' + str(pending) + '</div><div class="lbl">待上送</div></div>'
        '</div>')

    # 操作按钮
    buttons = []
    if pending > 0 and user["role"] == "township":
        buttons.append(
            '<form method="post" action="/tasks/' + str(task["id"]) + '/submit" style="display:inline">'
            '<button class="btn" type="submit">开始分批上送（' + str(pending) + ' 条）</button></form>')
    if fail > 0:
        buttons.append('<a class="btn warn" href="/tasks/' + str(task["id"]) + '/errors">查看错误清单（'
                       + str(fail) + '）</a>')
    buttons.append('<a class="btn" style="background:#6b7c8d" href="/">返回列表</a>')
    toolbar = '<div class="toolbar">' + "".join(buttons) + '</div>'

    # 批次表
    batch_html = ""
    if batches:
        brows = []
        for b in batches:
            badge = ('<span class="badge b-green">全部成功</span>' if b["fail_count"] == 0
                     else '<span class="badge b-red">部分退回</span>')
            brows.append(
                "<tr><td>第 " + str(b["batch_no"]) + " 批</td>"
                "<td>" + str(b["record_count"]) + "</td>"
                "<td class='ok'>" + str(b["success_count"]) + "</td>"
                "<td class='bad'>" + str(b["fail_count"]) + "</td>"
                "<td>" + badge + "</td>"
                "<td class='small'>" + esc(b["submitted_at"]) + "</td></tr>")
        batch_html = ('<h2>上送批次</h2><table><tr><th>批次</th><th>条数</th><th>成功</th>'
                      '<th>退回</th><th>结果</th><th>上送时间</th></tr>'
                      + "".join(brows) + "</table>")

    # 明细表
    rrows = []
    for r in records:
        if r["check_status"] == "OK":
            check_html = '<span class="badge b-green">通过</span>'
        else:
            check_html = '<span class="badge b-red" title="' + esc(r["check_message"]) + '">失败</span>'
        if r["check_status"] != "OK":
            submit_html = '<span class="small">未上送</span>'
        elif r["submit_status"] == "SUCCESS":
            submit_html = '<span class="ok">成功</span>'
        elif r["submit_status"] == "FAILED":
            submit_html = ('<span class="bad" title="' + esc(r["submit_message"]) + '">退回</span>')
        else:
            submit_html = '<span class="badge b-gray">待上送</span>'
        fail_reason = esc(r["check_message"] or r["submit_message"])
        rrows.append(
            "<tr><td>" + str(r["row_no"]) + "</td>"
            "<td>" + esc(r["name"]) + "</td>"
            "<td class='mono'>" + esc(mask_id(r["id_card"])) + "</td>"
            "<td class='mono'>" + esc(mask_card(r["bank_card"])) + "</td>"
            "<td>" + fmt_money(r["amount_cents"]) + "</td>"
            "<td>" + esc(r["township"]) + "</td>"
            "<td>" + check_html + "</td>"
            "<td>" + submit_html + "</td>"
            "<td>" + (str(r["batch_no"]) if r["batch_no"] else "-") + "</td>"
            "<td class='small'>" + fail_reason + "</td></tr>")
    detail = ("<table><tr><th>行号</th><th>补贴对象</th><th>身份证号</th><th>银行卡号</th>"
              "<th>金额(元)</th><th>乡镇</th><th>格式校验</th><th>上送结果</th><th>批次</th>"
              "<th>失败原因</th></tr>" + "".join(rrows) + "</table>")

    body = (_msg_html(msg) +
            '<div class="card"><h2>任务详情：' + esc(task["task_no"]) +
            ' <span class="small">' + esc(task["filename"]) + '｜' + esc(task["township"]) +
            '｜导入时间 ' + esc(task["created_at"]) + '</span></h2>'
            + summary + toolbar + batch_html + '<h2>名单明细</h2>' + detail + '</div>')
    return layout("任务详情", user, body)


def error_list_page(user, task, errors):
    rows = []
    for r in errors:
        rows.append(
            "<tr><td>" + str(r["row_no"]) + "</td>"
            "<td>" + esc(r["name"]) + "</td>"
            "<td class='mono'>" + esc(r["id_card"]) + "</td>"
            "<td class='mono'>" + esc(r["bank_card"]) + "</td>"
            "<td>" + fmt_money(r["amount_cents"]) + "</td>"
            "<td>" + esc(r["township"]) + "</td>"
            "<td>" + str(r["batch_no"] or "-") + "</td>"
            "<td class='bad'>" + esc(r["submit_message"]) + "</td></tr>")
    table = ("<table><tr><th>行号</th><th>补贴对象</th><th>身份证号</th><th>银行卡号</th>"
             "<th>金额(元)</th><th>乡镇</th><th>批次</th><th>退回原因</th></tr>"
             + ("".join(rows) if rows else
                "<tr><td colspan='8' style='text-align:center;color:#999'>无退回记录</td></tr>")
             + "</table>")
    body = (
        '<div class="card"><h2>错误清单：' + esc(task["task_no"]) + '</h2>'
        '<div class="toolbar">'
        '<a class="btn warn" href="/tasks/' + str(task["id"]) + '/errors.csv">下载错误清单 CSV</a>'
        '<a class="btn" style="background:#6b7c8d" href="/tasks/' + str(task["id"]) + '">返回任务详情</a>'
        '</div>'
        '<p class="small">以下为财政平台退回的记录，请更正后重新导入（退回记录不计入重复校验）。</p>'
        + table + '</div>')
    return layout("错误清单", user, body)
