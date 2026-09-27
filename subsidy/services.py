"""业务逻辑：名单导入、格式与重复校验、分批上送、错误清单。"""
import csv
import io
from datetime import datetime

from .db import get_conn
from .validators import check_id_card, check_bank_card, check_name, parse_amount
from . import fiscal_client

BATCH_SIZE = 20        # 每批上送条数
MAX_ROWS = 5000        # 单次导入行数上限
MAX_FILE_BYTES = 5 * 1024 * 1024  # 上传文件大小上限 5MB

# 表头别名（兼容常见写法）
HEADER_ALIASES = {
    "name":      ["补贴对象", "姓名", "对象名称"],
    "id_card":   ["身份证号", "身份证号码", "证件号码", "身份证"],
    "bank_card": ["银行卡号", "银行卡", "卡号"],
    "amount":    ["金额", "补贴金额", "补贴金额(元)", "补贴金额（元）"],
    "township":  ["乡镇", "所属乡镇", "乡镇街道"],
}
FIELD_CN = {"name": "补贴对象", "id_card": "身份证号", "bank_card": "银行卡号",
            "amount": "金额", "township": "乡镇"}


class ImportError_(Exception):
    """导入文件整体性问题（无法解析、缺列等）。"""


# ---------------------------------------------------------------- 解析

def parse_csv(content):
    """解析上传的 CSV 内容，返回 [{row_no, name, id_card, bank_card, amount_text, township}]"""
    text = None
    for enc in ("utf-8-sig", "gbk"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ImportError_("无法识别文件编码，请使用 UTF-8 或 GBK 编码的 CSV 文件")
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ImportError_("文件为空或只有表头，没有数据行")
    header = [h.strip() for h in rows[0]]
    colmap = {}
    for field, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if alias in header:
                colmap[field] = header.index(alias)
                break
    missing = [f for f in HEADER_ALIASES if f not in colmap]
    if missing:
        raise ImportError_("表头缺少必需列：" + "、".join(FIELD_CN[m] for m in missing))
    data = []
    for i, row in enumerate(rows[1:], start=2):  # 行号含表头，从 2 开始
        def cell(field, _row=row):
            idx = colmap[field]
            return _row[idx].strip() if idx < len(_row) else ""
        data.append({
            "row_no": i,
            "name": cell("name"),
            "id_card": cell("id_card").upper(),
            "bank_card": cell("bank_card").replace(" ", ""),
            "amount_text": cell("amount"),
            "township": cell("township"),
        })
    return data


# ---------------------------------------------------------------- 导入

def import_file(user, filename, content):
    """解析并校验导入文件，入库后返回 (task_id, 汇总)。"""
    rows = parse_csv(content)
    if len(rows) > MAX_ROWS:
        raise ImportError_("单次导入不能超过 %d 行" % MAX_ROWS)

    # 1) 逐行格式校验
    for r in rows:
        errors = []
        e = check_name(r["name"])
        if e:
            errors.append(e)
        e = check_id_card(r["id_card"])
        if e:
            errors.append(e)
        e = check_bank_card(r["bank_card"])
        if e:
            errors.append(e)
        cents, e = parse_amount(r["amount_text"])
        if e:
            errors.append(e)
        r["amount_cents"] = cents or 0
        if r["township"] != user["township"]:
            errors.append("乡镇“%s”与当前账号所属乡镇（%s）不符"
                          % (r["township"] or "空", user["township"]))
        r["errors"] = errors

    # 2) 文件内重复：格式正确的行之间按身份证号查重
    first_seen = {}
    for r in rows:
        if r["errors"]:
            continue
        key = r["id_card"]
        if key in first_seen:
            r["errors"].append("与文件内第%d行身份证号重复" % first_seen[key])
        else:
            first_seen[key] = r["row_no"]

    # 3) 与本乡镇历史有效记录查重（待上送或已上送成功的同身份证号）
    candidates = [r for r in rows if not r["errors"]]
    if candidates:
        conn = get_conn()
        placeholders = ",".join("?" for _ in candidates)
        sql = (
            "SELECT DISTINCT r.id_card FROM records r "
            "JOIN import_tasks t ON t.id = r.task_id "
            "WHERE t.township = ? AND r.check_status = 'OK' "
            "AND r.submit_status IN ('PENDING','SUCCESS') "
            "AND r.id_card IN (%s)" % placeholders
        )
        existing = {row[0] for row in conn.execute(
            sql, [user["township"]] + [r["id_card"] for r in candidates])}
        conn.close()
        for r in candidates:
            if r["id_card"] in existing:
                r["errors"].append("该身份证号已在本乡镇历史任务中导入（待上送或已上送）")

    # 4) 入库
    valid = [r for r in rows if not r["errors"]]
    conn = get_conn()
    with conn:
        today = datetime.now().strftime("%Y%m%d")
        seq = conn.execute(
            "SELECT COUNT(*) FROM import_tasks WHERE task_no LIKE ?",
            ("RW%s-%%" % today,)).fetchone()[0] + 1
        task_no = "RW%s-%03d" % (today, seq)
        cur = conn.execute(
            "INSERT INTO import_tasks (task_no, user_id, township, filename, total_rows, valid_rows, invalid_rows)"
            " VALUES (?,?,?,?,?,?,?)",
            (task_no, user["id"], user["township"], filename,
             len(rows), len(valid), len(rows) - len(valid)))
        task_id = cur.lastrowid
        for r in rows:
            conn.execute(
                "INSERT INTO records (task_id, row_no, name, id_card, bank_card, amount_cents,"
                " township, check_status, check_message) VALUES (?,?,?,?,?,?,?,?,?)",
                (task_id, r["row_no"], r["name"], r["id_card"], r["bank_card"],
                 r["amount_cents"], r["township"],
                 "OK" if not r["errors"] else "ERROR", "；".join(r["errors"])))
    conn.close()
    return task_id, {"total": len(rows), "valid": len(valid), "invalid": len(rows) - len(valid)}


# ---------------------------------------------------------------- 查询（含乡镇数据隔离）

def get_task_for_user(user, task_id):
    """按权限取任务：乡镇账号只能取本乡镇任务，取不到返回 None。"""
    conn = get_conn()
    if user["role"] == "admin":
        row = conn.execute("SELECT * FROM import_tasks WHERE id=?", (task_id,)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM import_tasks WHERE id=? AND township=?",
            (task_id, user["township"])).fetchone()
    conn.close()
    return dict(row) if row else None


def list_tasks(user):
    """任务列表：乡镇账号只见本乡镇，管理员见全部。"""
    sql = (
        "SELECT t.*, u.display_name AS operator,"
        " (SELECT COUNT(*) FROM records r WHERE r.task_id=t.id AND r.submit_status='SUCCESS') AS success_rows,"
        " (SELECT COUNT(*) FROM records r WHERE r.task_id=t.id AND r.submit_status='FAILED')  AS failed_rows"
        " FROM import_tasks t JOIN users u ON u.id = t.user_id"
    )
    conn = get_conn()
    if user["role"] == "admin":
        rows = conn.execute(sql + " ORDER BY t.id DESC").fetchall()
    else:
        rows = conn.execute(sql + " WHERE t.township=? ORDER BY t.id DESC",
                            (user["township"],)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_records(user, task_id, limit=1000):
    task = get_task_for_user(user, task_id)
    if not task:
        return None, None
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM records WHERE task_id=? ORDER BY row_no LIMIT ?", (task_id, limit)).fetchall()
    conn.close()
    return task, [dict(r) for r in rows]


def list_batches(user, task_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM batches WHERE task_id=? ORDER BY batch_no", (task_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_errors(user, task_id):
    """错误清单：上送被财政平台退回的记录。"""
    task = get_task_for_user(user, task_id)
    if not task:
        return None, None
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM records WHERE task_id=? AND check_status='OK' AND submit_status='FAILED'"
        " ORDER BY row_no", (task_id,)).fetchall()
    conn.close()
    return task, [dict(r) for r in rows]


# ---------------------------------------------------------------- 分批上送

def submit_task(user, task_id):
    """将任务中校验通过且待上送的记录分批上送财政平台，返回汇总；无权限返回 None。"""
    task = get_task_for_user(user, task_id)
    if not task:
        return None
    conn = get_conn()
    records = conn.execute(
        "SELECT * FROM records WHERE task_id=? AND check_status='OK' AND submit_status='PENDING'"
        " ORDER BY row_no", (task_id,)).fetchall()
    if not records:
        conn.close()
        return {"batches": 0, "success": 0, "failed": 0}

    success = failed = 0
    batch_count = 0
    with conn:
        for i in range(0, len(records), BATCH_SIZE):
            chunk = records[i:i + BATCH_SIZE]
            batch_count += 1
            results = fiscal_client.submit_batch(batch_count, [dict(r) for r in chunk])
            by_row = {res["row_no"]: res for res in results}
            b_ok = b_fail = 0
            for r in chunk:
                res = by_row[r["row_no"]]
                if res["success"]:
                    status, b_ok = "SUCCESS", b_ok + 1
                else:
                    status, b_fail = "FAILED", b_fail + 1
                conn.execute(
                    "UPDATE records SET submit_status=?, submit_message=?, batch_no=? WHERE id=?",
                    (status, res["message"], batch_count, r["id"]))
            conn.execute(
                "INSERT INTO batches (task_id, batch_no, record_count, success_count, fail_count)"
                " VALUES (?,?,?,?,?)",
                (task_id, batch_count, len(chunk), b_ok, b_fail))
            success += b_ok
            failed += b_fail
        conn.execute("UPDATE import_tasks SET status='DONE' WHERE id=?", (task_id,))
    conn.close()
    return {"batches": batch_count, "success": success, "failed": failed}
