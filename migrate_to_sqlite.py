# -*- coding: utf-8 -*-
"""
migrate_to_sqlite.py - 将 questions.json 迁移到 SQLite 数据库（v0.2.0）

使用方法:
    python migrate_to_sqlite.py             # 执行迁移
    python migrate_to_sqlite.py --dry-run   # 仅预览，不实际写库
    python migrate_to_sqlite.py --force     # 覆盖已存在的数据库

迁移流程:
    1. 读取 questions.json（缺失/损坏则给出明确提示并退出）
    2. 备份原 JSON 文件到 backups/ 目录
    3. 应用 schema.sql 创建表结构与索引
    4. 逐条插入数据，保留原始 ID（在一个事务内提交，失败自动回滚）
    5. 打印迁移摘要

注意:
    - 迁移后 questions.json 不会被删除（仅复制到 backups/），确认无误后可手动清理。
    - 默认不覆盖已存在的 .db 文件，需加 --force 才会覆盖（覆盖前同样备份）。
"""
import argparse
import datetime
import json
import os
import shutil
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_FILE = os.path.join(BASE_DIR, "questions.json")
DB_FILE = os.path.join(BASE_DIR, "questions.db")
SCHEMA_FILE = os.path.join(BASE_DIR, "schema.sql")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")

DEFAULT_CATEGORY = "未分类"


def _print(msg):
    """非交互环境下直接打印到 stdout。"""
    print(msg)


def _backup_json():
    """把当前 questions.json 复制到 backups/，返回备份文件名；无源文件返回 None。"""
    if not os.path.exists(JSON_FILE):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = f"questions_{ts}.json"
    shutil.copy2(JSON_FILE, os.path.join(BACKUP_DIR, name))
    return name


def _backup_db():
    """若已存在 .db 文件，备份后返回备份文件名；否则返回 None。"""
    if not os.path.exists(DB_FILE):
        return None
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = f"questions_{ts}.db"
    shutil.copy2(DB_FILE, os.path.join(BACKUP_DIR, name))
    return name


def load_json_questions():
    """读取 questions.json，返回列表；缺失或损坏时报错退出。"""
    if not os.path.exists(JSON_FILE):
        _print("[错误] 未找到 questions.json，无需迁移。")
        sys.exit(1)
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        _print(f"[错误] questions.json 解析失败: {e}")
        sys.exit(1)
    if not isinstance(data, list):
        _print("[错误] questions.json 顶层结构不是数组，无法迁移。")
        sys.exit(1)
    return data


def apply_schema(conn):
    """执行 schema.sql 建表与建索引。"""
    if not os.path.exists(SCHEMA_FILE):
        _print(f"[错误] 未找到 schema.sql: {SCHEMA_FILE}")
        sys.exit(1)
    with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
        conn.executescript(f.read())


def insert_questions(conn, items):
    """逐条插入，保留原始 ID。返回成功插入的条数。"""
    sql = (
        "INSERT INTO questions "
        "(id, title, description, timestamp, is_solved, solution, category) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    rows = []
    for item in items:
        # 兼容旧数据缺字段：与 Question.from_dict 一致地补默认值
        is_solved = item.get("is_solved", False)
        rows.append((
            item.get("id"),
            item.get("title", ""),
            item.get("description", ""),
            item.get("timestamp", ""),
            1 if is_solved else 0,
            item.get("solution", ""),
            item.get("category", DEFAULT_CATEGORY),
        ))
    conn.executemany(sql, rows)
    return len(rows)


def print_summary(items, db_path, json_backup, db_backup, dry_run):
    """打印迁移摘要。"""
    solved = sum(1 for it in items if it.get("is_solved", False))
    cats = sorted({it.get("category", DEFAULT_CATEGORY) for it in items})
    _print("\n" + "=" * 50)
    _print("迁移摘要" + ("（DRY-RUN 预览，未实际写库）" if dry_run else ""))
    _print("=" * 50)
    _print(f"数据条数   : {len(items)}")
    _print(f"已解决     : {solved}")
    _print(f"未解决     : {len(items) - solved}")
    _print(f"分类       : {', '.join(cats) if cats else '(无)'}")
    _print(f"目标数据库 : {db_path}")
    if json_backup:
        _print(f"JSON 备份  : backups/{json_backup}")
    if db_backup:
        _print(f"旧库备份   : backups/{db_backup}")
    _print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="将 questions.json 迁移到 SQLite 数据库"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅预览迁移结果，不实际创建/写入数据库",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="目标数据库已存在时覆盖（覆盖前自动备份）",
    )
    args = parser.parse_args()

    # 1. 读取 JSON
    items = load_json_questions()
    if not items:
        _print("[提示] questions.json 为空，将创建空数据库。")

    # 2. 检查目标库是否已存在
    db_backup = None
    if os.path.exists(DB_FILE) and not args.dry_run:
        if not args.force:
            _print(f"[中止] 数据库已存在: {DB_FILE}")
            _print("       如需覆盖，请加 --force（会先备份旧库）。")
            sys.exit(1)
        db_backup = _backup_db()
        os.remove(DB_FILE)
        _print(f"[覆盖] 已备份旧库到 backups/{db_backup} 并删除原库。")

    # 3. 备份 JSON（dry-run 不备份，避免产生副作用）
    json_backup = None
    if not args.dry_run:
        json_backup = _backup_json()
        if json_backup:
            _print(f"[备份] questions.json → backups/{json_backup}")

    # 4. dry-run：仅打印摘要后退出
    if args.dry_run:
        print_summary(items, DB_FILE, None, None, dry_run=True)
        return

    # 5. 建库 + 建表 + 插入（单事务，失败整体回滚）
    conn = sqlite3.connect(DB_FILE)
    try:
        apply_schema(conn)
        count = insert_questions(conn, items)
        conn.commit()
    except Exception as e:
        conn.rollback()
        _print(f"[错误] 迁移失败，已回滚: {e}")
        # 回滚后若库已创建则清理，避免留下空库
        conn.close()
        if os.path.exists(DB_FILE):
            os.remove(DB_FILE)
        sys.exit(1)

    # 6. 校验：读回条数
    cur = conn.execute("SELECT COUNT(*) FROM questions")
    actual = cur.fetchone()[0]
    conn.close()

    if actual != count:
        _print(f"[警告] 写入 {count} 条，但校验读回 {actual} 条，请检查。")
    else:
        _print(f"[完成] 已写入 {actual} 条数据到 {DB_FILE}")

    print_summary(items, DB_FILE, json_backup, db_backup, dry_run=False)


if __name__ == "__main__":
    main()
