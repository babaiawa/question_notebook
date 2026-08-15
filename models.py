# -*- coding: utf-8 -*-
"""
models.py - 数据层（模块化重构）

负责问题数据的模型定义和 JSON 文件读写。
CLI 版（question_notebook.py）和 Web 版（web_app.py）共用本模块，
数据逻辑只在这里维护一份，改 bug 只需改一处。

职责划分：
- 本模块：只关心"数据长什么样"和"怎么存取"，不关心界面
- 界面层（CLI/Web）：负责输入输出、菜单、路由，只调用本模块的函数
"""
import json
import datetime
import os

# 基于本文件所在目录定位数据文件（CLI/Web 都从项目根目录找）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "questions.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")
DEFAULT_CATEGORY = "未分类"


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
    - 文件损坏（JSON 解析失败）：备份为 .bak 后返回空列表，不崩溃
    """
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [Question.from_dict(item) for item in data]
    except json.JSONDecodeError:
        backup_file = DATA_FILE + ".bak"
        try:
            os.replace(DATA_FILE, backup_file)
            print(f"[警告] 数据文件损坏，已备份到 {backup_file}，将创建一个新的文件。")
        except OSError:
            print("[警告] 数据文件损坏且无法备份，将创建一个新的文件。")
        return []


def save_questions(questions):
    """将问题列表写入 JSON 文件（新问题自动分配 ID）。"""
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

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=4, ensure_ascii=False)
