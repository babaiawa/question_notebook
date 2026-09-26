# -*- coding: utf-8 -*-
"""
run_web.py - 网页版启动入口（未安装时的入口）

用法（在项目根目录执行）：
    python run_web.py
    然后浏览器打开 http://127.0.0.1:5000

它是做什么的？
    与 run_cli.py 同样的道理：真正的代码在包 `src/question_notebook/` 里，
    未安装时 Python 找不到它，所以这里先把 src/ 加进搜索路径，再调用包里的
    web.main()。

三种启动方式的对应关系（实际逻辑只有一处，都在包里）：

    python run_web.py                    ← 本文件（无需安装）
    python -m question_notebook.web      ← 包内模块（需先安装或 src 在路径中）
    question-notebook-web                ← 安装后注册的控制台命令

要想用环境变量启用登录密码，三种方式都支持，例如：

    Windows PowerShell:
        $env:QUESTION_NOTEBOOK_PASSWORD="你的密码"; python run_web.py

    Linux / macOS:
        QUESTION_NOTEBOOK_PASSWORD=你的密码 python run_web.py
"""
import os
import sys

# 项目根目录 = 本文件所在目录；代码在它下面的 src/
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# 注意：web 模块会导入 Flask，因此这一行要求已安装 Flask
# （python -m pip install -r requirements.txt）
from question_notebook.web import main  # noqa: E402  (必须在路径引导之后导入)

if __name__ == "__main__":
    main()
