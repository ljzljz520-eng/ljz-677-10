"""数据库连接与初始化（SQLite）"""
import sqlite3
from pathlib import Path

from flask import g
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent / 'subsidy.db'

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    township      TEXT NOT NULL,              -- 所属乡镇（数据权限依据）
    role          TEXT NOT NULL DEFAULT 'operator'   -- operator=乡镇经办人 / admin=县级管理员
);

CREATE TABLE IF NOT EXISTS import_tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_no       TEXT UNIQUE NOT NULL,       -- 任务编号
    user_id       INTEGER NOT NULL REFERENCES users(id),
    township      TEXT NOT NULL,              -- 任务所属乡镇
    filename      TEXT NOT NULL,
    total_count   INTEGER NOT NULL DEFAULT 0, -- 总行数
    valid_count   INTEGER NOT NULL DEFAULT 0, -- 校验通过
    invalid_count INTEGER NOT NULL DEFAULT 0, -- 校验失败
    success_count INTEGER NOT NULL DEFAULT 0, -- 上送成功
    failed_count  INTEGER NOT NULL DEFAULT 0, -- 上送失败
    status        TEXT NOT NULL DEFAULT 'VALIDATED',  -- VALIDATED=待提交 / COMPLETED=已完成
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS batches (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      INTEGER NOT NULL REFERENCES import_tasks(id),
    batch_no     INTEGER NOT NULL,            -- 任务内批次号
    record_count INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'SUBMITTED',   -- SUBMITTED/ACCEPTED/PARTIAL/REJECTED
    message      TEXT,
    submitted_at TEXT,
    finished_at  TEXT
);

CREATE TABLE IF NOT EXISTS subsidy_records (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id       INTEGER NOT NULL REFERENCES import_tasks(id),
    batch_id      INTEGER REFERENCES batches(id),
    row_number    INTEGER NOT NULL,           -- 文件内行号（从1开始，不含表头）
    name          TEXT NOT NULL,              -- 补贴对象姓名
    id_card       TEXT NOT NULL,              -- 身份证号
    bank_card     TEXT NOT NULL,              -- 银行卡号
    amount        REAL NOT NULL DEFAULT 0,    -- 发放金额
    township      TEXT NOT NULL,              -- 乡镇
    status        TEXT NOT NULL DEFAULT 'VALID',      -- VALID/INVALID/SUCCESS/FAILED
    error_message TEXT,                       -- 异常原因
    created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_records_task   ON subsidy_records(task_id);
CREATE INDEX IF NOT EXISTS idx_records_idcard ON subsidy_records(id_card);
CREATE INDEX IF NOT EXISTS idx_records_status ON subsidy_records(task_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_township ON import_tasks(township);
"""

# 演示账号：用户名, 密码, 姓名, 所属乡镇, 角色
DEFAULT_USERS = [
    ('admin',     'admin123', '县财政局管理员', '全县',   'admin'),
    ('chengguan', '123456',   '城关镇经办人',   '城关镇', 'operator'),
    ('dongcheng', '123456',   '东城镇经办人',   '东城镇', 'operator'),
    ('nanping',   '123456',   '南坪镇经办人',   '南坪镇', 'operator'),
]


def get_db():
    """请求级数据库连接（Flask g 缓存）"""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(exc=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def seed_users():
    conn = sqlite3.connect(DB_PATH)
    for username, password, display_name, township, role in DEFAULT_USERS:
        conn.execute(
            'INSERT OR IGNORE INTO users (username, password_hash, display_name, township, role)'
            ' VALUES (?,?,?,?,?)',
            (username, generate_password_hash(password), display_name, township, role))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    seed_users()
    print(f'数据库已初始化: {DB_PATH}')
