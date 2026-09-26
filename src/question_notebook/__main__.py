# -*- coding: utf-8 -*-
"""
__main__.py - 包的可执行入口

作用：让整个包可以直接用模块方式运行：

    python -m question_notebook

Python 的规则是：执行 `python -m 某包` 时，会自动运行该包里的 __main__.py。
这里把它转接到 CLI 的主函数 cli.main()，于是"模块方式"和"安装后的控制台命令"
走的是同一段代码，行为不会出现两套。

对照：
    python -m question_notebook          → 本文件 → cli.main()
    question-notebook                    → pyproject.toml 里注册的入口 → cli.main()
    python tests/test_question_notebook.py → 直接跑测试
"""
from .cli import main

if __name__ == "__main__":
    main()
