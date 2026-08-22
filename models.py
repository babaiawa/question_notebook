# -*- coding: utf-8 -*-
"""
models.py - 数据层

负责问题数据的模型定义、SQLite 数据库读写，以及备份/恢复/导出等数据操作。
CLI 版（question_notebook.py）和 Web 版（web_app.py）共用本模块，
数据逻辑只在这里维护一份，改 bug 只需改一处。

v0.2.0 起：存储从 questions.json 迁移到 SQLite（questions.db）。
一次性迁移请用 migrate_to_sqlite.py。界面层（CLI/Web）零改动，
本模块对外 API（Question / load_questions / save_questions / backup_data /
list_backups / restore_data / build_csv / data_lock）保持不变。

职责划分：
- 本模块：只关心"数据长什么样"和"怎么存取"，不关心界面
- 界面层（CLI/Web）：负责输入输出、菜单、路由，只调用本模块的函数
"""
import contextlib
import csv
import datetime
import io
import os
import re
import shutil
import sqlite3
import tempfile

# 基于本文件所在目录定位数据文件（CLI/Web 都从项目根目录找）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "questions.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")
DEFAULT_CATEGORY = "未分类"

# 备份文件名白名单：questions_YYYYMMDD_HHMMSS[_微秒].db
# （迁移后只产生 .db 备份；旧的 .json 备份不再列出/恢复，需用迁移脚本重新导入）
BACKUP_NAME_PATTERN = re.compile(r"^questions_\d{8}_\d{6}(_\d{6})?\.db$")

CSV_HEADERS = ["ID", "标题", "描述", "创建时间", "是否已解决", "解决方案", "分类"]

# 内联建表 SQL：与 schema.sql 保持一致。
# 内联而非读取 schema.sql，是为了在测试/打包等 schema.sql 不在同目录时仍能自举建库。
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    timestamp   TEXT    NOT NULL,
    is_solved   INTEGER NOT NULL DEFAULT 0
                CHECK (is_solved IN (0, 1)),
    solution    TEXT    NOT NULL DEFAULT '',
    category    TEXT    NOT NULL DEFAULT '未分类'
);
CREATE INDEX IF NOT EXISTS idx_questions_category  ON questions(category);
CREATE INDEX IF NOT EXISTS idx_questions_is_solved ON questions(is_solved);
CREATE INDEX IF NOT EXISTS idx_questions_timestamp ON questions(timestamp);
"""


class Question:
    """问题数据模型。包含标题、描述、解决状态、解决方案、分类、创建时间。"""
    def __init__(self, title, description="", is_solved=False, solution="", category=DEFAULT_CATEGORY):
        self.id = None  # 程序内部自动生成
        self.title = title
        self.description = description
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.is_solved = is_solved
        self.solution = solution
        self.category = category

    def to_dict(self):
        """转成字典（序列化用）。"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "timestamp": self.timestamp,
            "is_solved": self.is_solved,
            "solution": self.solution,
            "category": self.category
        }

    @classmethod
    def from_dict(cls, item):
        """从字典创建对象（反序列化用），兼容旧数据缺字段的情况。"""
        q = cls(
            title=item.get('title', ''),
            description=item.get('description', ''),
            is_solved=item.get('is_solved', False),
            solution=item.get('solution', ''),
            category=item.get('category', DEFAULT_CATEGORY)
        )
        q.id = item.get('id')
        q.timestamp = item.get('timestamp', '')
        return q


# ---------- 数据库连接 ----------

def _connect():
    """打开一个新的数据库连接。

    - timeout=5.0：遇到锁时最多等 5 秒（配合 data_lock 的应用层串行，
      正常情况下不会触发；这里作为兜底，避免偶发的 "database is locked"）
    - row_factory=Row：按列名取值，便于 _row_to_question
    - 每次调用新建连接，用完即关，不跨线程/跨请求复用
    """
    conn = sqlite3.connect(DATA_FILE, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_schema(conn):
    """建表与索引（IF NOT EXISTS 幂等，重复调用无副作用）。"""
    conn.executescript(_SCHEMA_SQL)


def _row_to_question(row):
    """sqlite3.Row → Question。is_solved 由 0/1 还原为布尔。"""
    q = Question(
        title=row["title"],
        description=row["description"],
        is_solved=bool(row["is_solved"]),
        solution=row["solution"],
        category=row["category"],
    )
    q.id = row["id"]
    q.timestamp = row["timestamp"]
    return q


def _handle_corrupt_db():
    """数据库损坏时的兜底：备份为 .bak 后返回空列表，不崩溃。

    与原 JSON 版的容错策略一致——把坏文件挪走，让后续操作能从干净状态重建。
    """
    backup_file = DATA_FILE + ".bak"
    try:
        os.replace(DATA_FILE, backup_file)
        print(f"[警告] 数据库文件损坏，已备份到 {backup_file}，将创建一个新的数据库。")
    except OSError:
        print("[警告] 数据库文件损坏且无法备份，将创建一个新的数据库。")
    return []


def load_questions():
    """从 SQLite 加载全部问题，返回 Question 对象列表（按 id 升序）。

    - 数据库不存在：返回空列表（不主动建库，首次 save 时才创建）
    - 数据库损坏（文件不是有效 SQLite 库）：备份为 .bak 后返回空列表，不崩溃
    - 首次访问：自动建表建索引（IF NOT EXISTS）
    """
    if not os.path.exists(DATA_FILE):
        return []

    try:
        conn = _connect()
    except sqlite3.DatabaseError:
        return _handle_corrupt_db()

    try:
        _ensure_schema(conn)
        rows = conn.execute(
            "SELECT id, title, description, timestamp, is_solved, solution, category "
            "FROM questions ORDER BY id"
        ).fetchall()
        return [_row_to_question(r) for r in rows]
    except sqlite3.DatabaseError:
        # 文件存在但不是有效 SQLite 库（如历史 JSON 残留、随机字节）
        return _handle_corrupt_db()
    finally:
        conn.close()


def save_questions(questions):
    """将问题列表写入数据库（整表替换语义，与原 JSON 全量覆盖一致）。

    - 新问题（id 为 None）自动分配 ID：max(已有 id) + 1 递增
    - 在单个事务内执行 DELETE 全表 → INSERT 全部，失败整体回滚
    - 跨进程安全由调用方的 data_lock() + 本事务共同保证
    """
    # ID 分配逻辑与原 JSON 实现完全一致（先扫一遍找 max，再给无 id 的递增）
    max_id = 0
    for q in questions:
        if q.id is not None and q.id > max_id:
            max_id = q.id
    for q in questions:
        if q.id is None:
            max_id += 1
            q.id = max_id

    conn = _connect()
    try:
        _ensure_schema(conn)
        conn.execute("BEGIN")
        conn.execute("DELETE FROM questions")
        if questions:
            conn.executemany(
                "INSERT INTO questions "
                "(id, title, description, timestamp, is_solved, solution, category) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (q.id, q.title, q.description, q.timestamp,
                     1 if q.is_solved else 0, q.solution, q.category)
                    for q in questions
                ],
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------- 备份与恢复 ----------

def backup_data():
    """创建数据快照到 backups/ 目录，返回备份文件名。

    文件名含微秒，避免同一秒内多次备份互相覆盖。
    备份内容为 .db 文件副本（调用方通常在 data_lock 内调用，无并发写）。
    """
    if not os.path.exists(DATA_FILE):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = f"questions_{timestamp}.db"
    shutil.copy2(DATA_FILE, os.path.join(BACKUP_DIR, name))
    return name


def list_backups():
    """列出全部备份文件名（新的在前）。"""
    if not os.path.isdir(BACKUP_DIR):
        return []
    return sorted(
        [f for f in os.listdir(BACKUP_DIR)
         if BACKUP_NAME_PATTERN.match(f)],
        reverse=True
    )


def restore_data(filename):
    """从备份文件恢复数据，返回 True/False。

    仅接受符合命名规范（questions_*.db）的纯文件名，拒绝路径穿越。
    恢复采用原子替换：先复制到同目录临时文件再 os.replace 覆盖目标库，
    避免恢复中途崩溃导致数据库文件损坏。
    """
    # 白名单校验：必须是纯文件名且匹配备份命名规范
    if not filename or not BACKUP_NAME_PATTERN.match(filename):
        return False
    backup_path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        return False
    # 原子替换：临时文件与目标同目录，保证 os.replace 是原子操作（同文件系统）
    fd, tmp_path = tempfile.mkstemp(dir=BASE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, 'wb') as f_out:
            with open(backup_path, 'rb') as f_in:
                shutil.copyfileobj(f_in, f_out)
        os.replace(tmp_path, DATA_FILE)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    return True


# ---------- 导出 ----------

def build_csv(questions):
    """生成 CSV 内容（含 UTF-8 BOM 头，Excel 可直接识别），返回字符串。"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_HEADERS)
    for q in questions:
        writer.writerow([
            q.id, q.title, q.description, q.timestamp,
            "是" if q.is_solved else "否", q.solution, q.category
        ])
    return '\ufeff' + output.getvalue()


# ---------- 统计聚合 ----------

def get_stats():
    """返回数据可视化用的聚合统计（分类分布 + 解决率 + 按月趋势）。

    所有统计都用 SQL 聚合一次性算出，避免在 Python 里遍历。
    返回字典：
        {
          "total": int,
          "solved": int,
          "open": int,
          "solve_rate": float,              # 0.0 ~ 1.0，total=0 时为 0
          "by_category": [                  # 按数量降序
            {"category": str, "total": int, "solved": int, "open": int}, ...
          ],
          "by_month": [                     # 按时间升序，格式 YYYY-MM
            {"month": str, "total": int, "solved": int}, ...
          ]
        }
    数据库不存在或损坏时返回零值结构（不抛异常）。
    """
    empty = {
        "total": 0, "solved": 0, "open": 0, "solve_rate": 0.0,
        "by_category": [], "by_month": [],
    }
    if not os.path.exists(DATA_FILE):
        return empty
    try:
        conn = _connect()
    except sqlite3.DatabaseError:
        return empty
    try:
        _ensure_schema(conn)
        total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if total == 0:
            return empty
        solved = conn.execute(
            "SELECT COUNT(*) FROM questions WHERE is_solved = 1"
        ).fetchone()[0]
        # 分类分布：一次 GROUP BY 同时拿到每类的总数与已解决数
        by_category = [
            {
                "category": r["category"],
                "total": r["total"],
                "solved": r["solved"],
                "open": r["total"] - r["solved"],
            }
            for r in conn.execute(
                "SELECT category, COUNT(*) AS total, "
                "SUM(is_solved) AS solved "
                "FROM questions GROUP BY category "
                "ORDER BY total DESC, category"
            )
        ]
        # 按月趋势：timestamp 形如 "YYYY-MM-DD HH:MM:SS"，取前 7 位得 "YYYY-MM"
        by_month = [
            {"month": r["month"], "total": r["total"], "solved": r["solved"]}
            for r in conn.execute(
                "SELECT substr(timestamp, 1, 7) AS month, "
                "COUNT(*) AS total, SUM(is_solved) AS solved "
                "FROM questions GROUP BY month ORDER BY month"
            )
        ]
        return {
            "total": total,
            "solved": solved,
            "open": total - solved,
            "solve_rate": solved / total,
            "by_category": by_category,
            "by_month": by_month,
        }
    except sqlite3.DatabaseError:
        return empty
    finally:
        conn.close()


# ---------- 跨进程锁 ----------

@contextlib.contextmanager
def data_lock():
    """跨进程写锁（基于文件锁），保护"读-改-写"事务。

    - Windows 用 msvcrt.locking，Linux/macOS 用 fcntl.flock
    - CLI 与 Web 同时运行、多进程/多 worker 部署时同样安全
    - 注意：文件锁不可重入，因此锁放在调用方的事务层
      （如 Web 写接口用 `with data_lock():` 包住整段读-改-写），
      save_questions 等函数内部不再加锁，避免同进程重入死锁
    - SQLite 自身也有锁，本锁在应用层先行串行化，避免 SQLite
      "database is locked" 错误（默认 busy_timeout=0 会立即失败）
    """
    lock_path = os.path.join(BASE_DIR, ".data.lock")
    # 确保锁文件存在且至少有 1 字节（msvcrt.locking 的要求）
    if not os.path.exists(lock_path):
        with open(lock_path, 'w', encoding='utf-8') as f:
            f.write('0')

    with open(lock_path, 'r+', encoding='utf-8') as f:
        if os.name == 'nt':
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
