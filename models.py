# -*- coding: utf-8 -*-
"""
models.py - 数据层

负责问题数据的模型定义、JSON 文件读写，以及备份/恢复/导出等数据操作。
CLI 版（question_notebook.py）和 Web 版（web_app.py）共用本模块，
数据逻辑只在这里维护一份，改 bug 只需改一处。

职责划分：
- 本模块：只关心"数据长什么样"和"怎么存取"，不关心界面
- 界面层（CLI/Web）：负责输入输出、菜单、路由，只调用本模块的函数
"""
import json
import datetime
import os
import re
import shutil
import tempfile

# 基于本文件所在目录定位数据文件（CLI/Web 都从项目根目录找）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "questions.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")
DEFAULT_CATEGORY = "未分类"

# 备份文件名白名单：questions_YYYYMMDD_HHMMSS[_\u5fae\u79d2].json
BACKUP_NAME_PATTERN = re.compile(r"^questions_\d{8}_\d{6}(_\d{6})?\.json$")

CSV_HEADERS = ["ID", "标题", "描述", "创建时间", "是否已解决", "解决方案", "分类"]


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


def load_questions():
    """从 JSON 文件加载问题列表。

    返回 Question 对象列表。
    - 文件不存在：返回空列表
    - 文件损坏（JSON 解析失败或顶层不是数组）：备份为 .bak 后返回空列表，不崩溃
    """
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 顶层必须是数组；合法 JSON 但结构不对（对象/字符串等）同样视为损坏
        if not isinstance(data, list):
            raise ValueError("数据文件顶层结构不是数组")
        return [Question.from_dict(item) for item in data]
    except (json.JSONDecodeError, ValueError, AttributeError):
        backup_file = DATA_FILE + ".bak"
        try:
            os.replace(DATA_FILE, backup_file)
            print(f"[警告] 数据文件损坏，已备份到 {backup_file}，将创建一个新的文件。")
        except OSError:
            print("[警告] 数据文件损坏且无法备份，将创建一个新的文件。")
        return []


def save_questions(questions):
    """将问题列表写入 JSON 文件（新问题自动分配 ID）。

    采用原子写入：先写临时文件再 os.replace 替换，避免写入中途
    进程崩溃/断电导致数据文件变成半个 JSON。
    """
    max_id = 0
    for q in questions:
        if q.id is not None and q.id > max_id:
            max_id = q.id

    items = []
    for q in questions:
        if q.id is None:
            max_id += 1
            q.id = max_id
        items.append(q.to_dict())

    # 临时文件与目标文件同目录，保证 os.replace 是原子操作（同文件系统）
    fd, tmp_path = tempfile.mkstemp(dir=BASE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, DATA_FILE)
    except BaseException:
        # 任何异常都清理临时文件，避免残留
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


# ---------- 备份与恢复 ----------

def backup_data():
    """创建数据快照到 backups/ 目录，返回备份文件名。

    文件名含微秒，避免同一秒内多次备份互相覆盖。
    """
    if not os.path.exists(DATA_FILE):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = f"questions_{timestamp}.json"
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

    仅接受符合命名规范（questions_*.json）的纯文件名，拒绝路径穿越。
    """
    # 白名单校验：必须是纯文件名且匹配备份命名规范
    if not filename or not BACKUP_NAME_PATTERN.match(filename):
        return False
    backup_path = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(backup_path):
        return False
    shutil.copy2(backup_path, DATA_FILE)
    return True


# ---------- 导出 ----------

def build_csv(questions):
    """生成 CSV 内容（含 UTF-8 BOM 头，Excel 可直接识别），返回字符串。"""
    import csv as _csv
    import io as _io
    output = _io.StringIO()
    writer = _csv.writer(output)
    writer.writerow(CSV_HEADERS)
    for q in questions:
        writer.writerow([
            q.id, q.title, q.description, q.timestamp,
            "是" if q.is_solved else "否", q.solution, q.category
        ])
    return '\ufeff' + output.getvalue()
