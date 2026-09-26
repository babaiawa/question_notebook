# -*- coding: utf-8 -*-
"""
paths.py - 路径解析（数据文件与环境相关路径的唯一来源）

为什么单独一个模块？
    在旧的平铺式布局里，数据文件就放在模型文件旁边，所以 models.py 里写
    一句 os.path.dirname(os.path.abspath(__file__)) 就够了。
    重组为标准包结构后，代码住进了 src/question_notebook/，而**用户的数据
    不应该跟着代码走**（更不该跑进 site-packages 里），因此"数据放哪"这件
    事必须单独想清楚，并且只能有一个地方定义它。

目录约定（重组后）：

    <项目根目录>/                     ← 你 git clone 下来的那个目录
    ├── questions.db                 ← 你的真实数据（默认就在这）
    ├── backups/                     ← 备份快照
    ├── exports/                     ← CSV 导出
    └── src/question_notebook/       ← 代码（这部分才是"包"）

三条规则：
    1. 数据默认放在**项目根目录**，与重组前完全一致 → 你现有的 questions.db
       不用搬家，打开就是原来的数据。
    2. 可用环境变量 QUESTION_NOTEBOOK_DATA_DIR 整体改写数据位置。
       用途：将来部署到服务器时，把数据放到 /var/lib/... 之类的持久化目录，
       升级代码时不会碰到数据。
    3. 计算结果都在**导入时**算好，存成模块级常量。这样 CLI、Web、测试三方
       拿到的是同一批值，不会出现"两处各算一遍、结果不一致"的问题。

⚠️ 部署提醒（默认值在"非可编辑安装"下的局限）：
    PROJECT_ROOT 是按"包目录往上两级"算出来的，它等于项目根目录**仅在以下两种情况**：
      - 直接在 git 仓库里运行（本项目的日常用法）；
      - 用 `pip install -e .` 可编辑安装（此时包仍指向仓库内的 src/）。
    如果换成普通安装 `pip install .`，代码会被复制到 site-packages，
    此时 PROJECT_ROOT 会指向 site-packages 附近——那里通常不可写（权限），
    而且升级/卸载包会把它清掉。
    因此：**凡是非可编辑安装的部署，都必须显式设置 QUESTION_NOTEBOOK_DATA_DIR**
    指向一个持久化目录。这是本模块刻意保留环境变量覆盖的原因。

⚠️ 测试注意：测试会重写 models.py 里的同名常量（如 models.DATA_FILE）来做数据
隔离。models.py 内部一律通过自己的模块属性访问这些路径，因此重写 models 一处
即可全局生效——这也是"路径唯一来源"带来的好处。
"""
import os

# ---------- 代码位置 ----------

# 本文件所在目录，也就是包目录 src/question_notebook/
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

# 项目根目录：包目录 → src/ → 项目根，所以往上两级
PROJECT_ROOT = os.path.dirname(os.path.dirname(PACKAGE_DIR))

# 包内的静态资源（schema.sql 与 Web 模板）
SCHEMA_FILE = os.path.join(PACKAGE_DIR, "schema.sql")
TEMPLATE_DIR = os.path.join(PACKAGE_DIR, "templates")

# ---------- 数据位置 ----------

# 允许通过环境变量整体改写数据目录（部署到服务器时用得上）
_ENV_DATA_DIR = os.environ.get("QUESTION_NOTEBOOK_DATA_DIR", "").strip()

# 数据目录：优先环境变量，否则用项目根目录
DATA_DIR = _ENV_DATA_DIR if _ENV_DATA_DIR else PROJECT_ROOT

# 数据文件路径。注意 BASE_DIR 这个名字是历史沿用（重组前它指数据所在目录），
# 保留此名是为了让"路径只有一处来源"这一点在 CLI/Web/测试里保持一致。
BASE_DIR = DATA_DIR

DATA_FILE = os.path.join(DATA_DIR, "questions.db")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
