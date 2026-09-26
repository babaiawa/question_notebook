# 工程规范 · Engineering Standards

> 本文档是 Question Notebook 项目的**统一规范手册**，写给「接手这个项目的人」。
> 如果你是编程新手，直接从头读：每个名词都配了「为什么需要它」的解释。
>
> 规范的目的不是增加负担，而是让三件事变得确定：
> ① 新电脑上能把项目跑起来；② 改代码不怕改坏；③ 每次改动都能被追溯。

---

## 目录

- [0. 三分钟速查表](#0-三分钟速查表)
- [1. 环境与依赖规范](#1-环境与依赖规范)
- [2. 包结构与导入规范（src 布局）](#2-包结构与导入规范src-布局)
- [3. 代码风格规范](#3-代码风格规范)
- [4. 测试规范](#4-测试规范)
- [5. CI 持续集成规范](#5-ci-持续集成规范)
- [6. 提交（commit）规范](#6-提交commit规范)
- [7. 分支与版本规范](#7-分支与版本规范)
- [8. 文档规范](#8-文档规范)
- [9. 日常操作手册](#9-日常操作手册)
- [10. 常见问题排查](#10-常见问题排查)
- [11. 规范符合性自检清单](#11-规范符合性自检清单)

---

## 0. 三分钟速查表

**我只要用这个工具，不改代码**（最省事）：

```bash
pip install -r requirements.txt     # 装依赖（只有 Flask 一个）
python run_cli.py                   # 命令行版
python run_web.py                   # 网页版 → http://127.0.0.1:5000
```

**我要改代码**（多两步）：

```bash
pip install -r requirements-dev.txt  # 装开发工具（ruff 挑错 + pytest 测试）
python tests/test_question_notebook.py   # 改完后跑测试，必须全绿
ruff check .                         # 检查代码写法问题
```

> 📌 注意命令都带 `run_*` / `tests/` 前缀：项目已从「平铺」改成标准的 `src/` 包布局，
> 旧的 `python question_notebook.py`、`python web_app.py`、`python test_qn.py` **都不存在了**，
> 而且**故意没有**留兼容旧路径的转发文件——敲旧命令会直接报"找不到文件"。
> 原因与三种等价启动方式见 [第 2 节](#2-包结构与导入规范src-布局)。

**我改完了要存档**：

```bash
git add -A
git commit -m "fix: 修复 Windows 下备份文件无法生成"
git push
```

---

## 1. 环境与依赖规范

### 1.1 名词解释

| 名词 | 说人话 |
| --- | --- |
| **依赖（dependency）** | 你的程序要用到的、别人写好的代码包。本项目只需要 `Flask`。 |
| **虚拟环境（venv）** | 给每个项目单独准备的一个"隔离的依赖存放区"，避免 A 项目要 Flask 2、B 项目要 Flask 3 时互相打架。 |
| **依赖清单** | 一张写明"本项目要哪些包"的清单，让新电脑能一键装齐。 |

### 1.2 本项目的依赖声明（两处，必须一致）

| 文件 | 作用 | 谁是权威 |
| --- | --- | --- |
| `pyproject.toml` 的 `[project] dependencies` | 项目身份证，现代 Python 的标准做法 | ✅ **权威来源** |
| `requirements.txt` | 给不熟悉现代打包工具的人用的简写 | 必须与之同步 |
| `pyproject.toml` 的 `[project.optional-dependencies] dev` | 只有开发者才需要的工具 | — |
| `requirements-dev.txt` | 上面那项的简写 | 必须与之同步 |

**为什么同一个东西要写两遍？** 因为两类人的习惯不同：用现代工具的人看 `pyproject.toml`，习惯老办法的人看 `requirements.txt`。为了防止"改了一处忘了另一处"，项目提供了自动校验脚本，CI 每次都会跑：

```bash
python scripts/check_deps.py     # 一致 → 退出码 0；不一致 → 退出码 1 并指明差异
```

> ⚠️ **规则**：新增/删除依赖时，**两个文件一起改**，然后跑一次上面的脚本确认。

### 1.3 依赖版本约束的写法

| 写法 | 含义 | 建议 |
| --- | --- | --- |
| `Flask>=2.3` | 至少 2.3，往上不限 | ✅ 推荐：既能用上新特性，又不会卡死 |
| `Flask==3.1.3` | 只能是这个版本 | 只在"必须锁死"时用 |
| `Flask` | 任意版本 | ⚠️ 不推荐：结果不可复现 |
| `Flask~=3.1` | 3.1.x，不能到 3.2 | 需要限制次版本时用 |

**为什么要写 `>=2.3` 而不是随便？** 因为 Web 层（`src/question_notebook/web.py`，重组前叫 `web_app.py`）用了 `app.json.ensure_ascii`（保证中文不乱码成 `\uXXXX`），这个属性 **Flask 2.3 才有**。写低了会在旧版本上报错。

### 1.4 虚拟环境（推荐，但非强制）

```bash
# 创建（只需一次）
python -m venv .venv

# 激活
.venv\Scripts\activate          # Windows PowerShell
source .venv/bin/activate       # Linux / macOS

# 之后所有 pip install / python 命令都作用于这个隔离环境
# 退出
deactivate
```

> `.venv/` 已在 `.gitignore` 中，**不会被提交**——虚拟环境里全是几百 MB 的第三方包，不该进版本库。

---

## 2. 包结构与导入规范（src 布局）

### 2.1 名词解释

| 名词 | 说人话 |
| --- | --- |
| **模块（module）** | 一个 `.py` 文件。比如 `models.py` 就是一个模块。 |
| **包（package）** | 装着多个模块的**文件夹**，标志是里面有个 `__init__.py`。本项目所有代码都在 `question_notebook` 这个包里。 |
| **src 布局（src layout）** | 把代码统一放进 `src/` 目录（`src/question_notebook/`），仓库根目录只留配置、文档、测试和数据。现代 Python 的推荐做法。 |
| **`__init__.py`** | 包的"身份证 + 前台"：有它才叫包；`import 包名` 时执行的就是它。本项目的 `__init__.py` 还负责把版本号和常用函数亮出来（`question_notebook.__version__` = `0.3.0`）。 |
| **`__main__.py`** | 包的"启动器"：`python -m 包名` 时 Python 自动运行这个文件。 |
| **入口点（entry point）/ 控制台命令（console script）** | 安装后能直接敲的短命令。在 `pyproject.toml` 的 `[project.scripts]` 里登记"命令名 = 哪个函数"。 |
| **相对导入（relative import）** | 包内部互相引用，写法 `from . import models`（那个 `.` 就是"我自己所在的包"）。 |
| **绝对导入（absolute import）** | 从包名开头的完整写法，如 `from question_notebook import models`。 |
| **`sys.path`** | Python 的"模块搜索路径清单"：`import` 时它会挨个目录去找。目录不在清单里，就算文件就在旁边也找不到。 |

### 2.2 为什么要改成 src 布局？

平铺布局（所有 `.py` 都在根目录）有个隐蔽的坑：**代码就在当前目录，`import` 总能成功**，于是你会以为"打包发布出去也能用"，直到别人装完发现少文件。src 布局把代码藏进 `src/` 里，逼着所有人（包括测试）走**真实的包导入路径**，打包错误在开发阶段就暴露出来。

代价是多了一层目录，于是需要三个"引导文件"（见 2.3）。**这是有意的取舍，不是多余的文件。**

### 2.3 目录结构（重组后的实际布局）

```
question_notebook/                      ← 项目根目录（你 git clone 下来的那个）
├── run_cli.py                          ← 未安装时启动命令行版：python run_cli.py
├── run_web.py                          ← 未安装时启动网页版：python run_web.py
├── conftest.py                         ← pytest 全局初始化：把 src/ 加进 sys.path
├── pyproject.toml                      ← 身份证 + 控制台命令 + 打包 + ruff/pytest/coverage 配置
├── requirements.txt / requirements-dev.txt
├── .editorconfig / .gitignore / .gitmessage
├── questions.db                        ← 你的真实数据，仍在仓库根目录（没有搬家）
├── src/question_notebook/              ← 代码（这里才是"包"）
│   ├── __init__.py                     ← 包的门面：版本号 + 对外接口
│   ├── __main__.py                     ← python -m question_notebook 的入口
│   ├── paths.py                        ← 路径解析：数据放哪的唯一来源
│   ├── models.py                       ← 数据层：模型 + SQLite 读写 + 备份/导出/统计
│   ├── cli.py                          ← 界面层：命令行菜单（原 question_notebook.py）
│   ├── web.py                          ← 界面层：Flask 路由（原 web_app.py）
│   ├── schema.sql                      ← 建表定义（代码的一部分，随代码发布）
│   └── templates/index.html            ← Web 前端页面
├── tests/test_question_notebook.py     ← 37 个测试用例（原 test_qn.py）
└── scripts/check_deps.py  scripts/migrate_to_sqlite.py
```

**四条硬性规则**：

1. **代码只写在 `src/question_notebook/` 里。** 根目录的文件（`run_cli.py`、`conftest.py`）只负责"把 `src/` 加进搜索路径然后转交控制权"，里面不写业务逻辑——逻辑只有一处，避免出现两套行为。
2. **包内部互相引用一律用相对导入**：`from . import models`、`from .paths import DATA_FILE`、`from .models import Question`。好处是包改名/被嵌进别的项目时不用改代码；反过来，包内写 `from models import ...` 是错误的**绝对导入**（`models` 不再是顶层模块名了）。
3. **包外部引用一律用绝对导入**：`from question_notebook import cli, models`（测试和脚本就是这么写的）。`src`、`tests`、`scripts` **不是**可互相导入的同级模块——`import src`、`from tests import ...` 这类写法不成立。
4. **不要重建旧的平铺文件。** `question_notebook.py`、`web_app.py`、`test_qn.py`、根目录的 `migrate_to_sqlite.py` 都已重命名迁移，**故意不留兼容转发文件**；需要兼容的是"命令"，做法见 2.4。

### 2.4 三种启动方式（行为完全一致）

真正干活的逻辑只有一处——`question_notebook.cli.main` 和 `question_notebook.web.main`。下面三种方式最终都调用它们：

| 方式 | 命令 | 前提 |
| --- | --- | --- |
| **未安装时（刚克隆下来）** | `python run_cli.py` / `python run_web.py` | 只需装 Flask（网页版才需要）；**在项目根目录执行**，脚本自己算路径，因此换目录也能跑 |
| **模块方式** | `python -m question_notebook` / `python -m question_notebook.web` | **包必须能被 import**：装过（`pip install -e .`），或者 `src` 已在 `sys.path` 里 |
| **模块方式（未安装也能用）** | `python -m src.question_notebook` | 无需安装，但**必须在项目根目录执行**（`src` 是靠"当前目录"才被当作命名空间找到的） |
| **安装后（正式推荐）** | `question-notebook` / `question-notebook-web` | 需要 `pip install -e .`（见 2.6） |

```bash
# 未安装：最省事的两种
python run_cli.py
python run_web.py

# 装过一次之后：短命令 + 模块方式
pip install -e .
question-notebook            # 等价于 python -m question_notebook
question-notebook-web        # 等价于 python -m question_notebook.web
python -m question_notebook
python -m question_notebook.web
```

> ⚠️ **容易踩的坑**：`python -m question_notebook` 在**未安装且 `src` 不在搜索路径**时会报
> `No module named question_notebook`——这不是坏了，而是 src 布局的正常表现。此时要么先用
> `pip install -e .`，要么改用 `python run_cli.py`，要么写成 `python -m src.question_notebook`。
> **日常开发建议直接用 `python run_cli.py` / `python run_web.py`**，理由见 2.6。
> 另外，`run_cli.py` / `run_web.py` / 测试脚本都会自己算出项目根目录，**从别的目录调用也不会找错包**；
> 而 `python -m src.question_notebook` 依赖"当前目录"，只能在项目根目录用。

启动网页版时若要启用登录密码，三种方式都支持同一个环境变量：

```powershell
# Windows PowerShell
$env:QUESTION_NOTEBOOK_PASSWORD="你的密码"; python run_web.py
```

```bash
# Linux / macOS
QUESTION_NOTEBOOK_PASSWORD=你的密码 python run_web.py
```

### 2.5 数据文件放哪？（`paths.py` 是唯一来源）

代码搬进了 `src/`，但**用户数据绝不跟着代码走**（更不该跑进 site-packages 里，那样升级代码会碰到数据）。规则集中写在 `src/question_notebook/paths.py` 一个文件里：

| 东西 | 位置 |
| --- | --- |
| 数据目录 | `paths.DATA_DIR` = 环境变量 `QUESTION_NOTEBOOK_DATA_DIR`（设了就用它），否则**项目根目录** |
| 你的记录 | `<数据目录>/questions.db` |
| 备份快照 | `<数据目录>/backups/` |
| CSV 导出 | `<数据目录>/exports/` |
| Flask 会话密钥 | `<数据目录>/.flask_secret` |
| 密码盐 | `<数据目录>/.auth_salt` |
| 跨进程写锁 | `<数据目录>/.data.lock` |

> 小细节：`.flask_secret` 在**第一次启动网页版**时自动生成；`.auth_salt` 只在设了登录密码
> （`QUESTION_NOTEBOOK_PASSWORD`）时才生成。免登录使用时看不到后者，属正常。代码里这两个路径
> 写的是 `paths.BASE_DIR`——它与 `DATA_DIR` 是**同一个值**（`BASE_DIR` 是重组前的历史名字，为兼容而保留）。

**三条要点**：

1. **数据默认位置与重组前完全一致**（就在项目根目录）——你现有的 `questions.db` 不用搬家，打开还是原来的数据。
2. **密钥文件故意不放进包里**：`.flask_secret`、`.auth_salt` 若住在包目录里，`pip install` 打包时可能被一起发布出去，等于把会话密钥公开；放在数据目录里则永远只属于你这台机器。
3. **只有一个地方定义路径**：CLI、Web、测试、脚本都从 `paths.py`（或经 `models` 转出）取路径。将来部署到服务器，只需设一个环境变量就能把数据挪到 `/var/lib/...` 这类持久化目录，代码一行都不用改。

```bash
# 把数据放到仓库外的目录（Linux/macOS 示例）
QUESTION_NOTEBOOK_DATA_DIR=/var/lib/question_notebook python run_web.py
```

### 2.6 打包与安装（含一条诚实的说明）

`pyproject.toml` 里与包结构相关的配置：

| 配置 | 作用 |
| --- | --- |
| `[project.scripts]` | 注册两个控制台命令：`question-notebook = "question_notebook.cli:main"`、`question-notebook-web = "question_notebook.web:main"` |
| `[tool.setuptools] package-dir = { "" = "src" }` | 告诉打包工具"代码在 `src/` 下，别到别处乱找" |
| `[tool.setuptools.packages.find] where = ["src"]` | 自动发现 `src/` 下的包 |
| `[tool.setuptools.package-data]` | 声明非 Python 文件也要打进包里：`question_notebook = ["templates/*.html", "schema.sql"]` |

> ⚠️ **`package-data` 不写会怎样？** 打包工具默认只收 `.py` 文件。漏了这行，别人装完会得到
> "代码装上了，但网页打不开 / 建不了表"的怪现象——`templates/index.html` 和 `schema.sql` 没被装进去。
> 新增任何非 `.py` 资源（模板、SQL、图标…）时，务必同步加进 `package-data`。

**关于 `pip install -e .`（可编辑安装）**：

```bash
pip install -e .            # 开发用：改代码立即生效，无需重装
pip install -e ".[dev]"     # 连开发工具（ruff / pytest / coverage）一起装
pip install .               # 普通安装（部署用）
```

它需要**可用的 setuptools 与网络/构建工具链**。在撰写本文档的实际环境里，`setuptools` 未安装、网络也不通，因此**可编辑安装这条路径没能当场验证**——这是如实说明，不是"应该可以"。

> 📌 正因为安装这件事不能当作前提，项目才额外提供了 `run_cli.py`、`run_web.py`，以及
> `conftest.py` / 测试文件里的 `sys.path` 引导：**零安装也能用、零安装也能跑测试**。
> 装不上不耽误干活；等有网络时再 `pip install -e .` 换取更短的命令。

---

## 3. 代码风格规范

### 3.1 名词解释

| 名词 | 说人话 |
| --- | --- |
| **PEP 8** | Python 官方的代码风格建议（缩进几个空格、怎么起名等）。 |
| **lint（静态检查）** | 不改功能，只挑"写法问题"的自动检查：多余的 import、定义了没用的变量、明显写错的名字。 |
| **ruff** | 本项目用的检查 + 排版工具，一个工具顶过去好几个，速度极快。 |
| **格式化（format）** | 按统一规则重新排列代码（缩进、空格、引号），不改逻辑。 |

### 3.2 硬性约定

| 项目 | 规定 | 依据 |
| --- | --- | --- |
| 缩进 | 4 个空格，**禁止 Tab** | PEP 8；混用会直接报 `IndentationError` |
| 编码 | UTF-8 | 项目含大量中文，别的编码会乱码 |
| 换行符 | LF（Git 在 Windows 检出时自动转 CRLF） | `.editorconfig` 已声明 |
| 文件末尾 | 保留一个空行 | Git diff 更干净 |
| 行尾 | 不允许有多余空格 | 同上 |
| 命名 | 模块/函数 `snake_case`；类 `PascalCase`；常量 `UPPER_CASE` | PEP 8 |
| 行宽 | 建议 ≤ 100 字符（**超长不报错**，中文注释难免超） | `pyproject.toml` 配置 |

以上除行宽外都由 `.editorconfig` 自动生效（大多数编辑器支持），**你不用手动管**。

### 3.3 ruff 的使用

```bash
ruff check .            # 只检查，列出问题（CI 跑的就是这个）
ruff check --fix .      # 检查并自动修复能修的（如 import 排序、多余空格）
ruff format .           # 按统一风格重新排版
```

**本项目启用的规则**（`pyproject.toml` → `[tool.ruff.lint]`）：

| 代号 | 管什么 | 举例 |
| --- | --- | --- |
| `E` | 代码格式错误 | 函数之间空行数量不对 |
| `W` | 代码格式警告 | 行尾多余空格 |
| `F` | **真·代码缺陷** | 导入了却没用、变量名拼错、重复定义 |
| `I` | import 排序与分组 | 标准库 / 第三方 / 本项目 三段分开排 |

**有意忽略的两条**：

- `E501`（单行过长）：中文注释和文档字符串天然容易超长，强制断行反而难读。
- `E402`（import 不在文件顶部）：重组为 `src` 布局后，**所有需要先引导路径的文件都只能这么写**——`run_cli.py`、`run_web.py`、`conftest.py`、`tests/test_question_notebook.py`、`scripts/migrate_to_sqlite.py` 都必须先 `sys.path.insert(...)` 把 `src/` 加进搜索路径，之后才能 `import question_notebook`。这不是坏味道，而是"零安装也能跑"的代价，属于有意为之。

**其他与包结构相关的 ruff 配置**（`pyproject.toml`）：

| 配置 | 内容 | 为什么 |
| --- | --- | --- |
| `[tool.ruff] extend-exclude` | `__pycache__`、`templates`、`backups`、`exports` | 前端 HTML 模板不是 Python 代码；后两个是用户数据目录，不该被检查 |
| `[tool.ruff.lint.isort] known-first-party` | `models`、`question_notebook`、`web_app`、`migrate_to_sqlite` | 告诉 import 排序器"哪些是本项目自己的模块"，好把标准库 / 第三方 / 本项目分成三段 |

> ⚠️ 注意 `known-first-party` 里目前仍留着 `models`、`web_app`、`migrate_to_sqlite` 这几个**旧的顶层模块名**，而 `scripts`、`tests` 并没有列进去——这与重组后的现实并不一致（包内引用现在都走相对导入，用不到这些名字）。此处**照实描述现状**，未擅自改动配置；是否清理属于独立的一次改动。

> 📌 **原则**：CI 里只做 `ruff check`（只报告），**不自动改代码**。机器不该偷偷改你的代码——要自动修，你自己在本机跑 `--fix` 并检查结果。

---

## 4. 测试规范

### 4.1 名词解释

| 名词 | 说人话 |
| --- | --- |
| **单元测试** | 一小段自动检查代码：给定输入，断言输出符合预期。 |
| **pytest** | 测试运行器：自动找出所有测试并跑一遍，汇总结果。 |
| **覆盖率（coverage）** | 测试到底执行了源码的百分之几，能指出哪些行从没被测过。 |
| **测试隔离** | 每个用例用自己独立的数据文件，互不影响，也绝不碰真实数据。 |

### 4.2 运行方式（两种都支持，结果一致）

```bash
python tests/test_question_notebook.py   # 推荐日常用：零依赖，只用 Python 标准库就能跑
pytest                                   # 装了一键工具后用：输出更清晰，支持筛选/重跑
```

两条命令都要**在项目根目录执行**（`pytest` 更严格，从别处跑可能收集不到用例）。它们都不需要先安装本项目：测试文件和根目录的 `conftest.py` 都会把 `<根目录>/src` 插进 `sys.path`。

pytest 的常用花样：

```bash
pytest -v                          # 显示每个用例名（配置里 addopts 已默认带上 -v）
pytest -k 备份                      # 只跑名字含"备份"的用例
pytest --lf                        # 只重跑上次失败的用例
pytest -x                          # 遇到第一个失败就停下
coverage run -m pytest && coverage report -m   # 看覆盖率 + 未覆盖的行号
```

> `pyproject.toml` 的 `[tool.pytest.ini_options]` 已声明 `testpaths = ["tests"]`（只到 `tests/` 找测试），
> 并用 `pythonpath = ["src"]` 把 `src/` 加进搜索路径——与根目录 `conftest.py` 的作用一致，属**双保险**。

### 4.3 硬性规则

1. **改完代码必须跑测试，全绿才能提交。** 当前基线：**37 个用例全部通过**。
2. **测试必须数据隔离。** 新写测试类时，继承 `QuestionNotebookTestCase`（已提供临时目录重定向与输出降噪），不要自己造轮子。测试里对包的引用一律用**绝对导入**：`from question_notebook import cli, models`（原因见 [第 2 节](#2-包结构与导入规范src-布局)）。
3. **禁止让测试写真实数据。** 测试数据一律落在项目内 `.tmp/` 目录（已 gitignore），用例结束自动删除，绝不碰 `questions.db`。测试通过重写 `models.DATA_FILE` 等常量来重定向路径——所以代码里读路径必须走 `models` 的模块属性，不要自己再拼一遍路径。
4. **缺陷修复必须配测试。** 修一个 bug 就补一个能复现它的用例——否则同一个坑会再踩一次。
5. **不许"假通过"。** 测试要真的验证行为（比如真去读文件确认落盘了），不能只断言"没报错"。

### 4.4 测试目录为什么放在项目内？（一条踩过的坑）

原实现用 `tempfile.mkdtemp()` 把测试数据写到**系统临时目录**。在受限/沙箱环境（以及部分 CI 容器）里，系统临时目录不可写，测试会直接崩：

```
PermissionError: [Errno 13] Permission denied: '...\.data.lock'
```

现改为在项目内 `.tmp/` 下自建唯一目录（`os.makedirs` + 随机后缀）。附带好处：所有测试产物集中在项目内，**随时可整体删除，不污染系统盘**。

**测试目录清理也做了加固**：原来用 `shutil.rmtree(..., ignore_errors=True)`，它在 Windows 上遇到只读文件或目录占用时会**删除失败却完全不报错**，结果 `.tmp/` 里悄悄堆积大量垃圾目录。现在改为 `_remove_tmpdir()`：先正常删，失败则去掉只读属性重试，仍失败就在标准错误里**明确警告**——不静默吞掉问题；若 `.tmp/` 已空还会顺手删掉它，不给项目留下空目录。

> 细节：`tempfile.mkdtemp()` 建的目录在部分沙箱下连后续写入都会被拦，所以这里刻意用 `os.makedirs` 自建目录；万一 `.tmp/` 不可写（只读介质），才退回系统临时目录兜底。

---

## 5. CI 持续集成规范

### 5.1 名词解释

**CI = Continuous Integration（持续集成）**。说人话：**每次你把代码推到 GitHub，云端机器人自动帮你跑一遍代码检查和全部测试**；有问题就在提交记录旁标红 ❌，没问题标绿 ✅。

对你最实际的价值：**你不需要记得"改完要跑测试"，机器替你记得。**

### 5.2 本项目流水线做什么

配置文件：`.github/workflows/ci.yml`，两个并行任务：

| 任务 | 内容 |
| --- | --- |
| **lint** | 用 `ruff check` 挑写法问题 + 用 `scripts/check_deps.py` 校验依赖声明一致 |
| **test** | 在 **Python 3.10 / 3.11 / 3.12 / 3.13** 四个版本上各跑一遍 37 个用例，并且**两种运行方式都测**（`pytest` 和 `python tests/test_question_notebook.py`） |

**为什么要在多个 Python 版本上测？** 因为项目声称支持 3.10+，那就必须在每个版本上验证，而不是"我电脑上是 3.14，能跑就算过"。矩阵中某个版本失败时，其他版本会继续跑完（`fail-fast: false`），一次看清全部问题。

> ⚠️ **待修的已知不一致（本文件不改代码，只如实记录）**：`.github/workflows/ci.yml` 的最后一步目前仍写着
> `python test_qn.py`，而该文件已重命名为 `tests/test_question_notebook.py`。按现状推送，
> **CI 的这一步会失败**（`pytest` 那一步不受影响，会正常跑完）。正确命令应为
> `python tests/test_question_notebook.py`。修它属于改 CI 配置的独立改动。

### 5.3 触发时机

| 时机 | 说明 |
| --- | --- |
| `push` 到 `main` | 直接推主干时自动跑 |
| 提 Pull Request | 合并前自动跑，防止坏代码进主干 |
| 手动触发 | GitHub 仓库页 → Actions → 选 CI → Run workflow |

### 5.4 本地没有网络时的说明

CI 的配置**只在你推送到 GitHub 之后才会执行**，本机不需要联网。若本机因网络受限装不上 `ruff`/`pytest`，可以：

- 日常验证用 `python tests/test_question_notebook.py`（零依赖，能跑通 37 个用例）；
- 把代码推到 GitHub，看 CI 页面的结果来确认 ruff 是否通过。

> 顺带一提：可编辑安装 `pip install -e .` 同样依赖网络与 setuptools，本机装不上时**不影响开发和测试**——
> 这正是 `run_cli.py` / `run_web.py` 与测试里的 `sys.path` 引导存在的意义（见 [2.6](#26-打包与安装含一条诚实的说明)）。

---

## 6. 提交（commit）规范

### 6.1 名词解释

**提交（commit）** = 给当前代码状态存一次档，同时写一句说明。**推送（push）** = 把本地的存档上传到 GitHub。

### 6.2 格式

```
<类型>(<范围>): <一句话说明>

<可选：为什么这么改、影响是什么>
```

- **类型**（必填，从下表选一个）
- **范围**（可选，写明改的是哪块，如 `web`、`cli`、`models`、`test`、`ci`）
- **说明**：说清"做了什么"，用**中文、动词开头、不超过 50 字**，**结尾不加句号**

### 6.3 类型对照表

| 类型 | 用在什么场合 | 例子 |
| --- | --- | --- |
| `feat` | 新增功能 | `feat(web): 新增按月趋势折线图` |
| `fix` | 修复 bug | `fix(models): 修复 Windows 下损坏库无法备份` |
| `docs` | 只改文档 | `docs: 补充局域网部署说明` |
| `style` | 只改格式（不影响功能） | `style: ruff 统一缩进与 import 顺序` |
| `refactor` | 重构（功能不变，改写法） | `refactor(cli): 抽取重复的菜单打印逻辑` |
| `perf` | 性能优化 | `perf(models): 统计改用 SQL 聚合` |
| `test` | 增改测试 | `test: 补充恢复接口的路径穿越用例` |
| `build` | 依赖或打包配置 | `build: 补充 pyproject.toml 依赖声明` |
| `ci` | 改 CI 配置 | `ci: 新增 GitHub Actions 测试矩阵` |
| `chore` | 其他杂活 | `chore: 更新 .gitignore` |

### 6.4 好例子 vs 坏例子（取自本项目真实历史）

| 评价 | 提交说明 | 问题 |
| --- | --- | --- |
| ❌ 坏 | `feat: 生成项目Code Wiki文档` | 同样的说明**连续出现了 7 次**，等于 7 个盒子贴同一张标签，日后无法定位改动 |
| ❌ 坏 | `修复` | 太笼统，看不出改了什么 |
| ❌ 坏 | `update` | 无信息量 |
| ✅ 好 | `fix(models): 损坏库备份前先关闭连接，修复 Windows 下 WinError 32` | 一眼看懂：改了哪块、为什么改、修了什么 |
| ✅ 好 | `docs: 同步认证与 CSRF 相关文档` | 明确是文档改动 |
| ✅ 好 | `test: 修复两个假通过测试（数据落盘 + 新增 _refresh 行为测试）` | 说清了动机 |

### 6.5 为什么值得认真写？

因为将来你（或别人）排查问题时，唯一的线索就是这些说明。写完说明只要 10 秒，而在一堆 `update` 里翻找一次改动可能要 30 分钟。

### 6.6 辅助工具（可选）

仓库提供了提交信息模板 `.gitmessage`，配置一次后每次提交都会看到提示：

```bash
git config commit.template .gitmessage
```

### 6.7 明确不做的事

- **不重写历史**：过去的提交保持原样，规范只约束**从现在起**的新提交。改写历史会让所有已克隆的人对不上号。
- **不提交私人数据**：`questions.db`（你的真实记录）、`.flask_secret`（会话密钥）、`.auth_salt`（密码盐）都已在 `.gitignore` 中。**千万别用 `git add -f` 强行提交它们**——这个仓库是公开的。
- **不留旧路径的兼容转发文件**：重组时 `question_notebook.py`→`cli.py`、`web_app.py`→`web.py`、`test_qn.py`→`tests/test_question_notebook.py` 都是一次性改到位，不做"两个文件都留着"的双份维护（理由见 [2.3](#23-目录结构重组后的实际布局)）。

---

## 7. 分支与版本规范

### 7.1 分支

| 分支 | 用途 |
| --- | --- |
| `main` | 主干，**始终保持可用**（测试全绿）。日常小改直接提交到这。 |
| `feat/xxx`、`fix/xxx` | 较大的、需要多步完成的改动，完成后合并回 `main` |

**规则**：绝不在 `main` 上留下"跑不起来"的状态。改动大就先开分支。

### 7.2 版本号

采用**语义化版本** `主版本.次版本.修订号`（`MAJOR.MINOR.PATCH`）：

| 位 | 什么时候加 | 例子 |
| --- | --- | --- |
| 主版本 | 不兼容的大改动 | v0.4.0 → v1.0.0 |
| 次版本 | 新增功能（向后兼容） | v0.2.0 → v0.3.0 |
| 修订号 | 修 bug | v0.2.0 → v0.2.1 |

**改版本号时要同步改的地方**（当前 `0.3.0`，src 布局重组后的版本）：

1. `pyproject.toml` → `[project] version`
2. `src/question_notebook/__init__.py` → `__version__`（**必须与前一项一字不差**：一个是打包元数据，一个是运行时自报的版本，对不上会让"到底装的哪个版本"变成悬案）
3. `README.md` → 「更新日志」新增一节
4. `ROADMAP.md` → 「当前状态」与「变更记录」

---

## 8. 文档规范

| 文档 | 写什么 | 什么时候更新 |
| --- | --- | --- |
| `README.md` | 项目是什么、怎么用、接口有哪些 | **功能变化时必更**（尤其 API 表与更新日志） |
| `STANDARDS.md`（本文） | 工程规范、提交规范 | 规范变化时 |
| `ROADMAP.md` | 版本规划与当前进度 | 每个版本开始/结束时 |
| `TUTORIAL.md` | 面向初学者的代码讲解 | 架构或核心逻辑变化时 |
| `CODE_WIKI.md` | 代码级详解（模块职责、关键函数） | 模块/函数变化时 |

**规则**：代码改了而文档没改 = 文档在说谎，比没有文档更糟。至少保证 `README.md` 的「API 文档」和「项目结构」与实际一致。

> ⚠️ 目录重构、文件改名、启动命令变化，都是**最容易让文档过期**的改动。这类改动要一次性扫一遍
> 所有文档与 CI 配置里出现的旧路径（`question_notebook.py`、`web_app.py`、`test_qn.py`、
> `migrate_to_sqlite.py`、`python -m` 的各种写法），别只改当前正在编辑的那一个文件。

---

## 9. 日常操作手册

### 9.1 第一次拿到这个项目

```bash
git clone https://github.com/babaiawa/question_notebook.git
cd question_notebook
pip install -r requirements.txt
python tests/test_question_notebook.py   # 应看到"通过 37 项"，说明环境没问题
                                         # （这一步连依赖都不用装：只用 Python 标准库）
                                         # 若没装 Flask，Web 相关用例会自动跳过而不是失败

# 然后就能直接用起来（无需安装本项目）
python run_cli.py                        # 命令行版
python run_web.py                        # 网页版 → http://127.0.0.1:5000
```

想用更短的命令，再补一步可编辑安装（需要 setuptools 与网络）：

```bash
pip install -e .          # 之后可用 question-notebook / question-notebook-web
```

### 9.2 改一个功能的完整流程

```bash
# 1. 开始前先确认基线是绿的
python tests/test_question_notebook.py

# 2. 改代码……（改 src/question_notebook/models.py、cli.py、web.py、
#    src/question_notebook/templates/index.html 等）
#    注意：包内部引用请用相对导入（from . import models），别写 from models import ...

# 3. 检查写法 + 跑测试
ruff check .
python tests/test_question_notebook.py

# 4. 补文档（README 的 API 表 / 更新日志；目录结构变了还要同步本文第 2 节与 CODE_WIKI）

# 5. 提交
git add -A
git commit -m "feat(web): 新增按月趋势图"
git push
```

### 9.3 修一个 bug

```bash
# 1. 先写一个能复现 bug 的测试（此时它应该失败）
# 2. 改代码让测试通过
# 3. 确认 37+1 个用例全绿
git commit -m "fix(cli): 修复搜索后数据未从磁盘刷新"
```

### 9.4 数据迁移（旧版 JSON → SQLite）

```bash
python scripts/migrate_to_sqlite.py             # 执行迁移
python scripts/migrate_to_sqlite.py --dry-run   # 仅预览，不实际写库
python scripts/migrate_to_sqlite.py --force     # 覆盖已存在的数据库（覆盖前先备份）
```

脚本会自己把 `src/` 加进搜索路径，因此**未安装也能跑**；它按 `paths.DATA_DIR` 的规则定位 `questions.json` / `questions.db` / `backups/`，从包内读取 `schema.sql`。

---

## 10. 常见问题排查

| 现象 | 原因 | 解决 |
| --- | --- | --- |
| `ModuleNotFoundError: No module named 'flask'` | 没装依赖 | `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'ruff'` | 没装开发工具 | `pip install -r requirements-dev.txt` |
| `No module named question_notebook` | 未安装本项目，却用了 `python -m question_notebook`（`src/` 不在搜索路径里） | 用 `python run_cli.py` / `python run_web.py`；或先 `pip install -e .`；或改用 `python -m src.question_notebook` |
| `can't open file 'question_notebook.py'`（或 `web_app.py` / `test_qn.py`） | 敲了重组前的旧命令，旧文件已重命名且**没有**兼容转发文件 | 换成 `python run_cli.py` / `python run_web.py` / `python tests/test_question_notebook.py` |
| `pip install -e .` 报缺少 setuptools / 卡在下载 | 可编辑安装需要构建工具链与网络 | 本机没有网络时**不必安装**：直接用 `run_cli.py` / `run_web.py` 和测试脚本即可；等到有网络时再装 |
| 装完包后网页打不开、或提示找不到模板 / `schema.sql` | `[tool.setuptools.package-data]` 没声明非 Python 文件，打包时被漏掉 | 确认 `question_notebook = ["templates/*.html", "schema.sql"]` 已声明，再重装 |
| `IndentationError` | 空格和 Tab 混用 | 让编辑器按 `.editorconfig` 用 4 空格缩进 |
| 测试报 `PermissionError ... .data.lock` | 测试数据写到了系统临时目录（受限环境不可写） | 测试类继承 `QuestionNotebookTestCase` 即可（已在项目内隔离） |
| 网页中文显示成 `\u4e2d\u6587` | Flask 版本低于 2.3 | 升级：`pip install -U "Flask>=2.3"` |
| 改动只有一行，diff 却显示整个文件 | 换行符被改了（CRLF↔LF）或被格式化工具重排 | 确认 `.editorconfig` 生效；`git config core.autocrlf true` |
| `pip install` 一直卡住无输出 | 网络受限，连不上 PyPI 或镜像源 | 换镜像源：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple ruff` |
| 提交时误把 `questions.db` 加进来了 | 私人数据进了暂存区 | `git rm --cached questions.db`（保留本地文件，仅从版本库移除） |
| 数据没在项目根目录，找不到 `questions.db` | 设置了 `QUESTION_NOTEBOOK_DATA_DIR`（数据目录被整体改写） | 查看该环境变量；数据文件与 `backups/`、`exports/`、密钥文件都在它指向的目录里 |

---

## 11. 规范符合性自检清单

每次准备提交前，逐条打勾：

- [ ] `python tests/test_question_notebook.py` 显示**全部通过**（当前基线 37 项，新增功能后应 ≥ 37）
- [ ] 若装了 ruff：`ruff check .` 无报错
- [ ] 新增/删除了依赖？→ 同步改了 `pyproject.toml` 与 `requirements.txt`，并跑了 `python scripts/check_deps.py`
- [ ] 新增了非 `.py` 资源（模板、SQL…）？→ 在 `[tool.setuptools.package-data]` 里声明了它
- [ ] 包内部引用用的是相对导入（`from . import models`），没有写成 `from models import ...`
- [ ] 修了 bug？→ 补了能复现它的测试用例
- [ ] 改了功能？→ 更新了 `README.md` 的接口表与更新日志
- [ ] 提交说明符合 [第 6 节](#6-提交commit规范) 的格式（类型 + 说明，中文，不加句号）
- [ ] `git status` 里**没有** `questions.db`、`.flask_secret`、`.auth_salt` 等私人数据
- [ ] 启动方式仍然有效：`python run_cli.py`、`python run_web.py`（装了包的话再加 `question-notebook`、`question-notebook-web`）
- [ ] 改过文件路径/文件名？→ 全局搜过一遍旧路径（含 `.github/workflows/ci.yml` 与各文档），没有残留

---

## 附：本规范落地的文件清单

| 文件 | 作用 |
| --- | --- |
| `pyproject.toml` | 项目身份证 + 控制台命令（`[project.scripts]`）+ 打包（setuptools src 配置 / package-data）+ ruff / pytest / coverage 配置 |
| `requirements.txt` | 运行依赖（普通用户） |
| `requirements-dev.txt` | 开发依赖（ruff / pytest / coverage） |
| `run_cli.py` | 未安装时的命令行入口：`python run_cli.py` |
| `run_web.py` | 未安装时的网页入口：`python run_web.py` |
| `conftest.py` | pytest 全局初始化：把 `<根目录>/src` 加进 `sys.path` |
| `src/question_notebook/__init__.py` | 包的门面：`__version__` = `0.3.0` + 对外接口 |
| `src/question_notebook/__main__.py` | `python -m question_notebook` 的入口 |
| `src/question_notebook/paths.py` | 路径解析：数据文件位置的唯一来源 |
| `src/question_notebook/models.py` | 数据层：模型 + SQLite 读写 + 备份/导出/统计 |
| `src/question_notebook/cli.py` | 命令行界面（原 `question_notebook.py`） |
| `src/question_notebook/web.py` | Flask 网页界面（原 `web_app.py`） |
| `src/question_notebook/schema.sql` | SQLite 表结构定义（随包发布） |
| `src/question_notebook/templates/index.html` | Web 前端页面（随包发布） |
| `tests/test_question_notebook.py` | 37 个测试用例（数据隔离 + 输出降噪；原 `test_qn.py`） |
| `.editorconfig` | 编辑器格式统一约定 |
| `.gitignore` | 排除私人数据、缓存、临时产物 |
| `.gitmessage` | 提交信息模板 |
| `scripts/check_deps.py` | 依赖声明一致性校验（CI 使用） |
| `scripts/migrate_to_sqlite.py` | 旧版 JSON → SQLite 数据迁移 |
| `.github/workflows/ci.yml` | CI 流水线（lint + 四版本测试矩阵） |

---

> 相关文档：[README.md](README.md)（项目说明）· [ROADMAP.md](ROADMAP.md)（路线图）· [TUTORIAL.md](TUTORIAL.md)（教学）· [CODE_WIKI.md](CODE_WIKI.md)（代码详解）
