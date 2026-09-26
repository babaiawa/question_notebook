# -*- coding: utf-8 -*-
"""
question_notebook - 问题笔记本

个人问题记录与知识管理工具，提供命令行（CLI）与网页（Web）两个界面，
两者共享同一份数据层与 SQLite 数据库，数据完全互通。

包结构（分层设计，依赖方向单向向下）：

    question_notebook/
    ├── paths.py      路径解析：数据文件与环境相关路径的唯一来源
    ├── models.py     数据层：Question 模型 + SQLite 读写 + 备份/导出/统计
    ├── cli.py        界面层：命令行菜单与交互
    ├── web.py        界面层：Flask 路由与 HTTP 接口
    ├── templates/    Web 前端页面
    ├── __main__.py   入口：python -m question_notebook → 启动 CLI
    └── schema.sql    SQLite 表结构定义

用法（在项目根目录，无需安装）：

    python -m question_notebook           # 命令行版
    python -m question_notebook.web       # 网页版 → http://127.0.0.1:5000

安装后可直接用控制台命令：

    pip install -e .
    question-notebook                     # 命令行版
    question-notebook-web                 # 网页版

注意：本包**不在导入时**加载 Flask。这样只装了标准库的环境也能用命令行版，
只有真正启动 Web 时才需要 Flask——依赖按需加载，不做无谓的强绑定。
"""

__version__ = "0.3.0"

# 数据层对外接口（不含 Web，避免 import 本包就要求装 Flask）
from .models import (  # noqa: F401
    DEFAULT_CATEGORY,
    Question,
    backup_data,
    build_csv,
    data_lock,
    get_stats,
    list_backups,
    load_questions,
    restore_data,
    save_questions,
)

__all__ = [
    "__version__",
    "DEFAULT_CATEGORY",
    "Question",
    "backup_data",
    "build_csv",
    "data_lock",
    "get_stats",
    "list_backups",
    "load_questions",
    "restore_data",
    "save_questions",
]
