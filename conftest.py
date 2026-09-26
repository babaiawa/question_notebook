# -*- coding: utf-8 -*-
"""
conftest.py - pytest 的全局初始化（放在项目根目录）

pytest 会在开始收集测试前自动导入本文件，因此这里适合做"所有测试都需要"的
准备工作。本项目只需要做一件事：**把 src/ 加进模块搜索路径**。

为什么需要它？
    代码在 src/question_notebook/ 下，测试在 tests/ 下，两者是分开的目录。
    测试要 `import question_notebook` 时，Python 默认只在"当前目录"和
    "已安装的包"里找，找不到 src/ 下的代码。把 src/ 加进搜索路径后，
    未安装也能正常导入。

为什么不用 `pip install -e .` 代替？
    可以，而且正式开发环境推荐那样做（见 STANDARDS.md）。但这个文件保证了
    **刚克隆下来、什么都没装的人也能直接跑测试**，降低上手门槛。
    （本项目的实际环境里 setuptools 可能缺失、网络也可能不通，那样 editable
    安装会失败——不能把"能跑测试"押在安装成功上。）
"""
import os
import sys

# conftest.py 就在项目根目录，所以它所在目录就是项目根目录
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

# 插到搜索路径最前面，确保优先用本仓库的代码（而不是同名第三方包）
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
