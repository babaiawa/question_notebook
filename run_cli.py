# -*- coding: utf-8 -*-
"""
run_cli.py - 命令行版启动入口（未安装时的入口）

用法（在项目根目录执行）：
    python run_cli.py

它是做什么的？
    真正干活的代码在包 `src/question_notebook/` 里。采用 src 布局后，Python
    默认**找不到**这个包（src/ 不在模块搜索路径里），除非先安装它：

        pip install -e .        →  之后可以直接敲命令 `question-notebook`

    但在"刚克隆下来、还没安装"的情况下，也需要一个能跑起来的入口。
    本文件就干这一件事：把 src/ 加进搜索路径，然后把控制权交给包里的 main()。

三种启动方式的对应关系（实际逻辑只有一处，都在包里）：

    python run_cli.py            ← 本文件（无需安装）
    python -m question_notebook  ← 包内 __main__.py（需先安装或 src 在路径中）
    question-notebook            ← 安装后注册的控制台命令（等价于上面两个）

这样做的好处：三种方式最终都调用 `question_notebook.cli.main`，
行为不会出现两套，改代码也只需改一处。
"""
import os
import sys

# 项目根目录 = 本文件所在目录；代码在它下面的 src/
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from question_notebook.cli import main  # noqa: E402  (必须在路径引导之后导入)

if __name__ == "__main__":
    main()
