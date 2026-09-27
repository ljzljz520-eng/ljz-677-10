"""数据库：连接、建表、初始账号。"""
import hashlib
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("SUBSIDY_DB") or os.path.join(BASE_DIR, "subsidy.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    township      TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'township'   -- township=乡镇经办人 / admin=县财政局
);

CREATE TABLE IF NOT EXISTS import_tasks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_no      TEXT UNIQUE NOT NULL,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    township     TEXT NOT NULL,
    filename     TEXT NOT NULL,
    total_rows   INTEGER NOT NULL DEFAULT 0,
    valid_rows   INTEGER NOT NULL DEFAULT 0,
    invalid_rows INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'VALIDATED',  -- VALIDATED=已校验待上送 / DONE=已上送
    created_at   TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS records (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id        INTEGER NOT NULL REFERENCES import_tasks(id),
    row_no         INTEGER NOT NULL,                 -- 在导入文件中的行号
    name           TEXT NOT NULL,
    id_card        TEXT NOT NULL,
    bank_card      TEXT NOT NULL,
    amount_cents   INTEGER NOT NULL,
    township       TEXT NOT NULL,
    check_status   TEXT NOT NULL,                    -- OK / ERROR
    check_message  TEXT NOT NULL DEFAULT '',
    submit_status  TEXT NOT NULL DEFAULT 'PENDING',  -- PENDING / SUCCESS / FAILED
    submit_message TEXT NOT NULL DEFAULT '',
    batch_no       INTEGER
);

CREATE TABLE IF NOT EXISTS batches (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       INTEGER NOT NULL REFERENCES import_tasks(id),
    batch_no      INTEGER NOT NULL,
    record_count  INTEGER NOT NULL,
    success_count INTEGER NOT NULL DEFAULT 0,
    fail_count    INTEGER NOT NULL DEFAULT 0,
    submitted_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_records_task   ON records(task_id);
CREATE INDEX IF NOT EXISTS idx_records_idcard ON records(id_card);
CREATE INDEX IF NOT EXISTS idx_tasks_township ON import_tasks(township);
"""

# 初始账号（首次建库时写入）
USERS = [
    ("admin",     "Admin@2026", "县财政局管理员", "县财政局", "admin"),
    ("chengdong", "Town@2026",  "城东镇经办人",   "城东镇",   "township"),
    ("chengxi",   "Town@2026",  "城西镇经办人",   "城西镇",   "township"),
    ("hekou",     "Town@2026",  "河口乡经办人",   "河口乡",   "township"),
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000).hex()


def init_db():
    conn = get_conn()
    with conn:
        conn.executescript(SCHEMA)
        for username, password, display, township, role in USERS:
            exists = conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone()
            if not exists:
                salt = os.urandom(16).hex()
                conn.execute(
                    "INSERT INTO users (username, password_hash, salt, display_name, township, role) VALUES (?,?,?,?,?,?)",
                    (username, hash_password(password, salt), salt, display, township, role),
                )
    conn.close()


def verify_user(username, password):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    if row and hash_password(password, row["salt"]) == row["password_hash"]:
        return dict(row)
    return None


def get_user(user_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
