# Question Notebook · 问题笔记本

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![Flask](https://img.shields.io/badge/Flask-3.x-000000)
![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20Web-38BDF8)
![Storage](https://img.shields.io/badge/Storage-SQLite-003B57)

个人问题记录与知识管理工具。支持 **命令行（CLI）** 与 **Web 界面** 双端操作，帮助用户系统化地记录学习与工作中遇到的问题、追踪解决进度、沉淀解决方案，并支持分类管理、全文检索、数据备份与导出。

---

## 目录

- [项目简介](#项目简介)
- [功能特性](#功能特性)
- [架构设计](#架构设计)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [数据存储](#数据存储)
- [API 文档](#api-文档)
- [测试](#测试)
- [项目结构](#项目结构)
- [路线图](#路线图)
- [更新日志](#更新日志)

> 📖 **教学文档**：想系统学习这个项目的代码实现（数据模型、CLI、Web、架构、测试），请阅读 [TUTORIAL.md](TUTORIAL.md)，含配套动手练习。
> 🗺️ **路线规划**：项目的版本规划与演进方向，详见 [ROADMAP.md](ROADMAP.md)。
> 📚 **代码知识库**：面向开发者的代码级详解（模块职责、关键函数、业务流程），详见 [CODE_WIKI.md](CODE_WIKI.md)。
> 📐 **工程规范**：依赖管理、代码风格、测试、CI、提交规范（含新手解释），详见 [STANDARDS.md](STANDARDS.md)。

---

## 项目简介

Question Notebook 是一个轻量级的问题记录系统，核心价值在于：

1. **随时记录**：以最小成本捕捉日常遇到的技术问题与学习疑问
2. **闭环管理**：从记录 → 分析 → 解决 → 沉淀方案，形成完整闭环
3. **高效检索**：多关键词搜索、状态筛选、分类浏览，快速定位历史问题
4. **数据自主**：数据以 SQLite 数据库存储于本地，用户完全掌控，支持一键备份与恢复

CLI 与 Web 两个前端共享同一数据层与数据库文件，数据完全互通，用户可根据场景自由切换。

## 功能特性

| 模块 | 功能 | 说明 |
|------|------|------|
| 记录 | 添加问题 | 支持标题、详细描述、分类三个维度 |
| 管理 | 编辑问题 | 可修改标题、描述、分类、解决方案，未修改字段保持不变 |
| 管理 | 标记已解决 | 为问题补充解决方案与心得 |
| 管理 | 删除问题 | 二次确认机制，防止误删 |
| 检索 | 全文搜索 | 匹配标题/描述/解决方案/分类，忽略大小写 |
| 检索 | 多关键词搜索 | 空格分隔多个关键词，AND 逻辑（全部命中） |
| 检索 | 状态筛选 | 按未解决/已解决过滤 |
| 检索 | 分类浏览 | 按分类聚合查看 |
| 数据 | 自动持久化 | 数据实时写入本地 SQLite 数据库 |
| 数据 | 备份与恢复 | 带时间戳快照备份（.db 副本），覆盖前二次确认 |
| 数据 | 导出 CSV | UTF-8 BOM 编码，Excel 直接打开无乱码 |
| 数据 | 数据可视化 | 分类分布柱状图 + 解决率环形图，原生 Canvas 绘制，零第三方依赖 |
| 兼容 | 迁移工具 | 提供 `scripts/migrate_to_sqlite.py`，将历史 `questions.json` 一键迁入 SQLite |
| 安全 | 密码认证 | 可选：设置环境变量后启用登录，密码 PBKDF2 哈希存储 |
| 安全 | CSRF 防护 | 所有写操作校验 X-CSRF-Token，防止跨站请求伪造 |

## 架构设计

项目采用**分层模块化**设计，代码集中在 `src/question_notebook/` 包内，遵循单一职责原则：

```
┌──────────────────────────────────────────────────┐
│                  界面层（表现层）                  │
│  ┌─────────────────┐    ┌──────────────────┐    │
│  │  CLI 命令行界面  │    │  Web 界面 (Flask) │    │
│  │  cli.py         │    │  web.py          │    │
│  └────────┬────────┘    │  + templates/    │    │
│           │             └────────┬─────────┘    │
└───────────┼──────────────────────┼──────────────┘
            │        调用           │
┌───────────▼──────────────────────▼──────────────┐
│              数据层（models.py）                  │
│  Question 模型 · 序列化 · SQLite 读写             │
│  （含损坏自动备份、schema 自举建表）               │
└───────────────────────┬──────────────────────────┘
                        │ 路径从哪来？
              ┌─────────▼──────────┐
              │   paths.py         │
              │  数据/密钥位置唯一来源│
              └────────────────────┘
```

**设计原则：**

- **单一职责**：数据层只负责数据存取，界面层只负责交互展示
- **依赖单向**：界面层依赖数据层，数据层不依赖任何界面实现
- **存储隔离**：数据存取逻辑集中在 `models.py`，未来迁移至 PostgreSQL 时界面层无需改动
- **路径唯一来源**：数据文件与密钥的位置只在 `paths.py` 定义一次，代码目录与数据目录严格分离

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | 标准库为主，唯一第三方运行时依赖是 Flask |
| Web 框架 | Flask ≥ 2.3 | 轻量级 WSGI 应用框架（2.3+ 才支持 `app.json.ensure_ascii`） |
| 前端 | 原生 HTML/CSS/JavaScript | 无框架依赖，深色响应式界面 |
| 存储 | SQLite | 标准库 `sqlite3`，单文件数据库，零配置 |
| 测试 | pytest / unittest | 37 个用例；也可直接 `python tests/test_question_notebook.py` 零依赖运行 |
| 代码检查 | ruff | 静态检查（E/W/F/I 规则）+ 格式化，配置见 `pyproject.toml` |
| CI | GitHub Actions | 四版本 Python 矩阵自动测试 + ruff 检查 |

## 快速开始

### 环境要求

- Python 3.10 及以上
- Web 版需要 Flask（命令行版不需要）

### 安装依赖

依赖声明在 `requirements.txt`，一条命令装齐：

```bash
python -m pip install -r requirements.txt
```

> 只有开发/改代码时才需要额外工具（ruff 挑错 + pytest 测试）：
> ```bash
> python -m pip install -r requirements-dev.txt
> ```

### 启动 CLI

```bash
python run_cli.py
```

### 启动 Web

```bash
python run_web.py
```

启动后浏览器访问 **http://127.0.0.1:5000**。

首次运行会在项目根目录自动创建 SQLite 数据库 `questions.db`（首次写入时建表）。

### 三种启动方式（等价，按需选）

代码采用 **src 布局**（代码在 `src/question_notebook/`，数据与配置在根目录）。因此未安装时不能直接 `python -m question_notebook`，需要按下面任一方式启动：

| 方式 | 命令 | 前提 |
|------|------|------|
| **① 启动脚本**（推荐） | `python run_cli.py`<br>`python run_web.py` | 只需装 Flask |
| **② 模块方式** | `python -m question_notebook`<br>`python -m question_notebook.web` | 需先 `pip install -e .`（或 `src` 已在 `PYTHONPATH` 中） |
| **③ 控制台命令** | `question-notebook`<br>`question-notebook-web` | 需先 `pip install -e .` |

三种方式最终都调用同一个函数（CLI 为 `question_notebook.cli.main`，Web 为 `question_notebook.web.main`），行为完全一致。

若要安装（可获得方式 ②③，开发时推荐可编辑安装）：

```bash
python -m pip install -e .
```

> 说明：可编辑安装需要 `setuptools` 与可用的软件源。本项目的开发环境中这两者均不可用，因此**安装路径未经实际验证**；上面三种方式中的 ① 已实测可用，且不依赖任何安装步骤。

### 从旧版 JSON 迁移（可选）

若你用过 v0.1.x 的 JSON 存储版本，升级到 v0.2.0 后可用迁移脚本把 `questions.json` 一键导入 SQLite：

```bash
python scripts/migrate_to_sqlite.py             # 执行迁移
python scripts/migrate_to_sqlite.py --dry-run   # 仅预览，不写库
python scripts/migrate_to_sqlite.py --force     # 覆盖已存在的 questions.db（先备份）
```

迁移会：备份原 JSON 到 `backups/` → 应用包内 `schema.sql` 建表 → 单事务导入数据 → 读回校验。原有 ID 完整保留。迁移确认无误后可删除 `questions.json`。

### 启用密码认证（可选）

Web 版默认**免登录**（仅适合本机 `127.0.0.1` 使用）。若要在局域网/公网部署，请设置密码：

```bash
# Linux / macOS
QUESTION_NOTEBOOK_PASSWORD=你的密码 python run_web.py

# Windows (PowerShell)
$env:QUESTION_NOTEBOOK_PASSWORD="你的密码"; python run_web.py
```

> 安装后也可用控制台命令：`QUESTION_NOTEBOOK_PASSWORD=你的密码 question-notebook-web`

| 环境变量 | 说明 |
|---------|------|
| `QUESTION_NOTEBOOK_PASSWORD` | 登录密码。设置后启用登录页，未设置则免登录 |
| `QUESTION_NOTEBOOK_SECRET` | 可选，Flask 会话签名密钥；不设置则首次运行自动生成 `.flask_secret` 持久化保存 |

## 使用指南

### CLI 主菜单

```
=========================
     问题笔记本主菜单
=========================
  1. 查看所有问题
  2. 添加新问题
  3. 标记问题为已解决
  4. 删除问题
  5. 搜索问题
  6. 编辑问题
  7. 备份与恢复
  8. 按状态筛选
  9. 导出 CSV
  10. 按分类查看
  0. 退出程序
=========================
```

### Web 界面

- **问题卡片列表**：分类/状态徽章、时间、描述、解决方案一目了然
- **实时搜索**：输入即过滤，支持多关键词（空格分隔）
- **组合筛选**：状态筛选与分类筛选可叠加
- **弹窗操作**：添加/编辑/标记解决/删除确认/备份恢复均为模态框交互
- **导出下载**：CSV 文件由浏览器直接下载
- **数据可视化**：可折叠面板，展开即绘制分类分布柱状图（已解决/未解决分段堆叠）与解决率环形图，随数据变化实时刷新

### 备份与恢复

- 备份文件存放于 `backups/` 目录，命名格式：`questions_YYYYMMDD_HHMMSS_微秒.db`
- 恢复操作会覆盖当前全部数据，执行前有二次确认
- Web 版恢复功能含路径穿越防护，仅允许选择备份目录内文件

## 数据存储

数据默认存储于**项目根目录**的 SQLite 数据库 `questions.db`，单文件、零配置。表结构定义在 [src/question_notebook/schema.sql](src/question_notebook/schema.sql)（`models.py` 内部也内联了一份等价的建表 SQL，确保无 schema.sql 时仍能自举建库）。

**数据与密钥的位置可配置**，规则统一由 `src/question_notebook/paths.py` 决定：

| 环境变量 | 作用 | 默认值 |
|---------|------|--------|
| `QUESTION_NOTEBOOK_DATA_DIR` | 数据目录（`questions.db`、`backups/`、`exports/`、`.flask_secret`、`.auth_salt` 都基于它） | 项目根目录 |

```bash
# 把数据放到项目外的独立目录（例如部署到服务器时）
# Windows PowerShell
$env:QUESTION_NOTEBOOK_DATA_DIR="D:\qn-data"; python run_cli.py
# Linux / macOS
QUESTION_NOTEBOOK_DATA_DIR=/var/lib/question-notebook python run_cli.py
```

> 为什么代码在 `src/` 而数据在根目录？代码目录是可分发的只读资源，数据是"这台机器的状态"。两者混在一起会导致升级或安装时丢失数据，详见 [TUTORIAL.md](TUTORIAL.md) 第 1.8 节。

### 表结构（`questions` 表）

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| `id` | INTEGER | PRIMARY KEY | 问题唯一标识，自增 |
| `title` | TEXT | NOT NULL | 问题标题，必填 |
| `description` | TEXT | NOT NULL DEFAULT '' | 问题详细描述 |
| `timestamp` | TEXT | NOT NULL | 创建时间，`YYYY-MM-DD HH:MM:SS` |
| `is_solved` | INTEGER | NOT NULL DEFAULT 0, CHECK IN (0,1) | 解决状态（0/1，SQLite 无布尔型） |
| `solution` | TEXT | NOT NULL DEFAULT '' | 解决方案 |
| `category` | TEXT | NOT NULL DEFAULT '未分类' | 问题分类 |

索引：`idx_questions_category`、`idx_questions_is_solved`、`idx_questions_timestamp`（支撑筛选与后续可视化统计）。

### 字段说明（对应 `Question` 模型）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 问题唯一标识，自动分配，自增 |
| `title` | str | 问题标题，必填 |
| `description` | str | 问题详细描述，可为空 |
| `timestamp` | str | 创建时间，格式 `YYYY-MM-DD HH:MM:SS` |
| `is_solved` | bool | 解决状态（库内存 0/1，读取时还原为布尔） |
| `solution` | str | 解决方案，未解决时为空字符串 |
| `category` | str | 问题分类，默认 `未分类` |

> **容错**：数据库文件损坏（非有效 SQLite 格式）时自动备份为 `questions.db.bak` 后重建，不崩溃。

## API 文档

Web 版提供 RESTful API，所有接口返回 JSON（中文原样输出，无 `\u` 转义）。

| 方法 | 路径 | 功能 | 请求体 |
|------|------|------|--------|
| GET | `/` | 渲染 Web 界面 | - |
| GET | `/api/auth-status` | 查询认证状态（是否启用、是否已登录） | - |
| GET | `/api/csrf` | 下发 CSRF Token | - |
| POST | `/api/login` | 登录（校验密码） | `{password}` |
| POST | `/api/logout` | 登出 | - |
| GET | `/api/questions` | 获取全部问题 | - |
| POST | `/api/questions` | 添加问题 | `{title, description, category}` |
| PUT | `/api/questions/<id>` | 编辑问题（含标记解决） | `{title?, description?, category?, is_solved?, solution?}` |
| DELETE | `/api/questions/<id>` | 删除问题 | - |
| GET | `/api/stats` | 聚合统计（分类分布、解决率、按月趋势） | - |
| GET | `/api/export` | 导出 CSV（附件下载） | - |
| POST | `/api/backup` | 创建备份快照 | - |
| GET | `/api/backups` | 列出备份文件 | - |
| POST | `/api/restore` | 从备份恢复 | `{filename}` |

**约定：**
- 添加问题时 `title` 必填，为空返回 `400` 及错误信息
- 编辑接口仅更新请求体中存在的字段（部分更新）
- 操作不存在的 ID 返回 `404`
- 恢复接口校验文件名，拒绝路径穿越
- **CSRF**：除 `GET/HEAD/OPTIONS` 外的所有请求须携带请求头 `X-CSRF-Token`（值来自 `/api/csrf`），否则返回 `403`；`/api/login` 豁免
- **认证**：启用密码后，未登录访问受保护接口返回 `401`

### `/api/stats` 响应示例

```json
{
  "total": 4,
  "solved": 2,
  "open": 2,
  "solve_rate": 0.5,
  "by_category": [
    { "category": "未分类", "total": 3, "solved": 2, "open": 1 },
    { "category": "数据库", "total": 1, "solved": 0, "open": 1 }
  ],
  "by_month": [
    { "month": "2026-07", "total": 3, "solved": 2 },
    { "month": "2026-08", "total": 1, "solved": 0 }
  ]
}
```

- `solve_rate`：`0.0 ~ 1.0`，`total=0` 时为 `0`
- `by_category`：按 `total` 降序排列，供柱状图使用
- `by_month`：按时间升序（`YYYY-MM`），供趋势图使用
- 数据库不存在或损坏时返回零值结构（`total=0`、数组为空），不抛异常

## 测试

项目内置 **37 个自动化测试**，覆盖数据层、CLI 界面层与 Web 层（含认证与 CSRF）。两种运行方式结果一致：

```bash
python tests/test_question_notebook.py   # 推荐日常用：零依赖，只需 Python 标准库
pytest                                   # 装了 pytest 后可用：支持 -k 筛选、--lf 重跑失败项
```

> 测试文件在 `tests/` 下，会自己把 `src/` 加进模块搜索路径，因此**不需要安装**任何东西即可运行。

pytest 常用参数：

```bash
pytest -k 备份                    # 只跑名字含"备份"的用例
pytest --lf                      # 只重跑上次失败的用例
coverage run -m pytest && coverage report -m   # 看测试覆盖率与未覆盖行号
```

**测试覆盖：**
- 数据层：模型序列化往返、读写循环、schema 默认值、损坏数据库容错（含非 SQLite 文件）、备份文件名唯一性、恢复文件名白名单、CSV 生成、统计聚合（分类分布/解决率/按月趋势，含损坏库容错）
- CLI 层：完整业务流程（增→改→搜→解决→删）、备份恢复往返、CSV 导出（含 BOM 校验）、分类浏览、多关键词搜索
- Web 层：增删改查全链路、空 body/非法 JSON、CSRF 缺失/错误拒绝、登录成功/失败、登出失效、免登录默认态、`/api/stats` 随数据变化实时更新

> **测试数据隔离**：所有用例的数据写入项目内 `.tmp/` 临时目录（已在 `.gitignore` 中），
> 用完自动删除，**绝不会读写你真实的 `questions.db`**。测试输出会自动静音 CLI 菜单打印，
> 只保留最终结论（如「共 37 项 | 通过 37 项」）。
>
> 开发规范（改代码前后该做什么、提交怎么写）见 [STANDARDS.md](STANDARDS.md)。

## 项目结构

采用 **src 布局**：代码集中在 `src/question_notebook/` 包内，数据与配置留在根目录。

```
question_notebook/
├── run_cli.py                 # 启动入口：命令行版（未安装时用，推荐）
├── run_web.py                 # 启动入口：网页版（未安装时用，推荐）
├── conftest.py                # pytest 初始化：把 src/ 加进模块搜索路径
│
├── src/question_notebook/     # 【代码包】
│   ├── __init__.py            # 包说明 + 版本号 + 数据层 API 重导出
│   ├── __main__.py            # python -m question_notebook → CLI
│   ├── paths.py               # 路径唯一来源（数据/密钥位置，支持环境变量覆盖）
│   ├── models.py              # 数据层：Question 模型 + SQLite 读写 + 跨进程锁
│   ├── cli.py                 # CLI 界面层
│   ├── web.py                 # Web 界面层（Flask 路由）
│   ├── schema.sql             # SQLite 表结构定义（建表/索引）
│   └── templates/
│       └── index.html         # Web 前端页面
│
├── tests/
│   └── test_question_notebook.py   # 37 个自动化测试（数据层 + CLI + Web）
├── scripts/
│   ├── check_deps.py          # 依赖声明一致性校验（CI 使用）
│   └── migrate_to_sqlite.py   # JSON → SQLite 一次性迁移脚本
│
├── .github/workflows/
│   └── ci.yml                 # CI：ruff 检查 + 四版本 Python 测试矩阵
├── pyproject.toml             # 项目配置（依赖 + 启动命令 + ruff/pytest/coverage 配置）
├── requirements.txt           # 运行依赖（Flask）
├── requirements-dev.txt       # 开发依赖（ruff + pytest + coverage）
├── .editorconfig              # 编辑器格式约定（缩进/编码/换行符）
├── .gitignore                 # 排除私人数据、缓存与临时产物
├── .gitmessage                # 提交信息模板
│
├── questions.db               # SQLite 数据库（首次运行自动生成，不入版本库）
├── .flask_secret              # Flask 会话签名密钥（自动生成，不入版本库）
├── .auth_salt                 # 密码哈希盐（启用认证后自动生成，不入版本库）
├── .tmp/                      # 测试临时目录（跑测试时自动创建并清理）
├── backups/                   # 备份目录（.db 快照，自动创建，不入版本库）
├── exports/                   # CSV 导出目录（自动创建，不入版本库）
│
├── ROADMAP.md                 # 路线图（版本规划与演进方向）
├── STANDARDS.md               # 工程规范（依赖/风格/测试/CI/提交，含新手解释）
├── TUTORIAL.md                # 教学文档（代码讲解 + 动手练习，面向新手）
├── CODE_WIKI.md               # 代码级知识库（模块职责 + 关键函数）
└── README.md                  # 项目文档
```

## 路线图

项目按版本规划演进，当前状态与完整规划详见 [ROADMAP.md](ROADMAP.md)：

| 版本 | 主题 | 状态 |
|------|------|------|
| v0.1.0 | 个人工具（CLI + Web + 模块化） | ✅ 已发布 |
| v0.2.0 | 数据升级（SQLite 迁移） | ✅ 已完成 |
| v0.2.x | 数据可视化 + 工程规范化 | ✅ 已完成 |
| v0.3.0 | 标准化包结构（src 布局） | 🚧 进行中 |
| v0.3.0 | 社区化（用户系统 + 问答） | 📋 规划中 |
| v0.4.0 | 社会问题采集（数据接入） | 📋 规划中 |
| v1.0.0 | 关联与发布（平台化） | 📋 规划中 |

## 更新日志

### 2026-09-26 · v0.3.0 标准化包结构（src 布局重组）

**目录结构（本次为破坏性变更，旧的文件路径已不存在）**
- 代码迁入 `src/question_notebook/` 包：`question_notebook.py` → `cli.py`、`web_app.py` → `web.py`、`models.py` 与 `schema.sql`、`templates/` 一并入包
- 测试迁入 `tests/test_question_notebook.py`（原 `test_qn.py`）；迁移脚本迁入 `scripts/migrate_to_sqlite.py`
- 新增 `src/question_notebook/__init__.py`（包说明 + `__version__` + 数据层 API 重导出，导入时不加载 Flask）、`__main__.py`（支持 `python -m question_notebook`）

**路径与数据安全**
- 新增 `src/question_notebook/paths.py`：路径的**唯一来源**，把"代码目录"与"数据目录"彻底分开
- 数据默认仍在项目根目录（你的 `questions.db` 无需搬家），新增 `QUESTION_NOTEBOOK_DATA_DIR` 环境变量可整体改写数据位置
- `.flask_secret` 与 `.auth_salt` 由代码目录移到数据目录：密钥属于"机器状态"，不该随代码分发或写进安装目录

**启动方式（原 `python question_notebook.py` / `python web_app.py` 已不可用）**
- 新增 `run_cli.py` / `run_web.py`：未安装即可用的启动入口（会引导模块搜索路径）
- `pyproject.toml` 注册控制台命令 `question-notebook` 与 `question-notebook-web`（src 布局打包配置 + 非 Python 文件声明）
- 三种方式最终都调用同一个 `main()`，行为一致

**测试与工具**
- 测试文件与 `conftest.py` 自带路径引导，**不安装任何东西**即可运行；`pyproject.toml` 增加 `pythonpath = ["src"]`
- 迁移脚本改为从包内定位 `schema.sql`，并以 `paths.DATA_DIR` 为数据基准
- 37 个测试全部通过（数据层 / CLI / Web 覆盖范围不变）

### 2026-09-26 · v0.2.2 工程规范化

本次不改变任何功能与启动方式，只补齐工程底座（详细规范见 [STANDARDS.md](STANDARDS.md)）。

**依赖管理**
- 新增 [pyproject.toml](pyproject.toml)：项目元信息 + 依赖声明 + ruff/pytest/coverage 配置
- 新增 `requirements.txt`（运行依赖）与 `requirements-dev.txt`（开发依赖），此前项目没有任何依赖清单
- 新增 [scripts/check_deps.py](scripts/check_deps.py)：校验两个依赖文件的声明一致，CI 每次执行

**代码质量**
- 引入 ruff 静态检查（规则 E/W/F/I，忽略影响中文可读性的 E501 与测试必需的 E402）
- 新增 `.editorconfig`：统一缩进（4 空格）、编码（UTF-8）、换行符（LF）
- 重写 `.gitignore`：分类整理，补齐测试缓存、覆盖率报告、虚拟环境等条目

**测试改进**
- 修复测试数据落盘位置：由系统临时目录改为项目内 `.tmp/`，**消除了受限环境下的 `PermissionError`**
  （原实现在沙箱/部分 CI 容器中因系统临时目录不可写而整个测试套件失败）
- 抽出公共基类 `QuestionNotebookTestCase`：统一临时目录重定向与输出降噪，三个测试类不再重复代码
- 测试输出自动静音 CLI 菜单打印，结尾输出一行结论（`共 37 项 | 通过 37 项`），结果一眼可见
- 支持 pytest 与直接运行测试文件两种方式，结果一致

**CI 与协作规范**
- 新增 [.github/workflows/ci.yml](.github/workflows/ci.yml)：ruff 检查 + Python 3.10/3.11/3.12/3.13 四版本测试矩阵，两种运行方式都验证
- 新增 [STANDARDS.md](STANDARDS.md)：依赖、风格、测试、CI、提交、分支版本、文档规范（含面向新手的名词解释）
- 新增 `.gitmessage` 提交信息模板，按 Conventional Commits 约定（`feat:` / `fix:` / `docs:` 等）

### 2026-08-22 · v0.2.1 数据可视化

**统计聚合**
- 数据层新增 `get_stats()`：用 SQL 聚合一次性算出分类分布（`GROUP BY category`）、解决率、按月趋势（`substr(timestamp,1,7)`），数据库损坏时返回零值结构不抛异常
- Web 层新增 `GET /api/stats` 接口（带认证）

**数据可视化（Web 前端）**
- 新增可折叠的「数据可视化」面板，展开即拉取 `/api/stats` 并绘制
- 分类分布柱状图：每类一根柱，已解决（绿）/未解决（橙）分段堆叠，顶部标总数、下方标 `已解决/未解决`
- 解决率环形图：圆心显示百分比，下方图例标数量
- 全部用原生 Canvas 绘制，零第三方依赖，随数据增删改实时刷新

**测试**
- 新增 3 个用例：`get_stats` 单元测试（聚合正确性）、损坏库容错、`/api/stats` 端点随数据变化实时更新

### 2026-08-22 · v0.2.0 数据升级（SQLite 迁移）

**存储迁移**
- 数据存储从 `questions.json` 迁移到 SQLite 数据库（`questions.db`），单文件、零配置
- 新增 [schema.sql](schema.sql)：定义 `questions` 表结构与 3 个索引（category / is_solved / timestamp）
- 新增 [migrate_to_sqlite.py](migrate_to_sqlite.py)：JSON → SQLite 一次性迁移脚本，支持 `--dry-run` 预览与 `--force` 覆盖

**数据层改造（`models.py`）**
- `load_questions` / `save_questions` 内部实现切换为 SQLite，对外 API 完全不变，界面层零改动
- `save_questions` 改为单事务（DELETE 全表 → INSERT 全部），失败整体回滚；ID 分配逻辑不变
- 备份/恢复文件名后缀 `.json` → `.db`，恢复采用原子替换（临时文件 + `os.replace`）
- 损坏容错：非有效 SQLite 文件自动备份为 `.bak` 后重建
- 保留 `data_lock` 跨进程锁（应用层串行化，避免 SQLite "database is locked"）

**测试**
- 更新数据层测试：新增 schema 默认值校验、SQLite 文件格式校验；损坏容错用例适配非 SQLite 文件场景

### 2026-08-16 · v0.1.2 Web 安全加固

**认证与 CSRF**
- 新增可选密码认证：设置 `QUESTION_NOTEBOOK_PASSWORD` 环境变量即启用登录，密码 PBKDF2 哈希存储、防时序攻击
- 新增 CSRF 防护：所有写请求须携带 `X-CSRF-Token` 头，防止跨站请求伪造
- 新增 `/api/csrf`、`/api/login`、`/api/logout`、`/api/auth-status` 四个接口
- Flask 会话密钥支持环境变量注入，否则持久化到 `.flask_secret`

**并发与数据一致性**
- 写锁由进程内 `threading.Lock` 升级为跨进程文件锁 `data_lock`（CLI 与 Web 并发写安全）
- CLI 每次读操作前从磁盘刷新内存快照，与 Web 端数据实时互通

**测试**
- 测试覆盖扩展至 Web 层（认证 + CSRF + 全链路），用例数增至 34 个

### 2026-08-15 · v0.1.1 稳定性与安全修复

**数据安全**
- 写入改为原子操作（临时文件 + `os.replace`），进程中断不会损坏数据文件
- 数据文件顶层结构异常（非数组）时自动备份重建，不再崩溃
- 备份文件名精确到微秒，同一秒内多次备份不再互相覆盖

**并发与接口**
- Web 端写操作加线程锁，消除并发读-改-写竞态导致的数据丢失
- API 请求体为空/非 JSON 时返回友好错误（原为 500）
- 恢复接口文件名白名单校验，彻底拒绝路径穿越

**架构**
- 备份/恢复/CSV 导出逻辑下沉至数据层 `models.py`，CLI 与 Web 共用，兑现"数据逻辑单一维护"

### 2026-08-15 · v0.1.0 首个正式版本

**功能**
- 问题记录与管理：添加、查看、编辑、删除（二次确认）、标记已解决
- 检索：多关键词搜索（AND 逻辑）、状态筛选、分类浏览
- 分类体系：支持自定义分类，默认 `未分类`，历史数据自动兼容
- 数据安全：JSON 损坏自动备份重建（`.bak`）、一键备份与恢复（时间戳快照）
- 数据导出：CSV（UTF-8 BOM，Excel 直接打开无乱码）

**界面**
- CLI 命令行版（`question_notebook.py`）
- Web 版（`web_app.py`）：Flask 服务 + 浏览器界面 + 完整 REST API

**架构**
- 分层模块化：数据层（`models.py`）与界面层（CLI/Web）解耦，数据逻辑单一维护
- 数据文件基于脚本目录定位，支持任意工作目录运行

**测试**
- 内置 9 个自动化测试用例（数据层 + CLI 层），数据隔离运行，不影响真实数据
