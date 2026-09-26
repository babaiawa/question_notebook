# Question Notebook · 问题笔记本

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![Flask](https://img.shields.io/badge/Flask-3.x-000000)
![Interface](https://img.shields.io/badge/Interface-CLI%20%2B%20Web-38BDF8)
![Storage](https://img.shields.io/badge/Storage-SQLite-003B57)

个人问题记录与知识管理工具。支持 **命令行（CLI）** 与 **Web 界面** 双端操作，帮助用户系统化地记录学习与工作中遇到的问题、追踪解决进度、沉淀解决方案，并支持分类管理、全文检索、数据备份与导出。

---

## 文档导航

| 文档 | 回答什么问题 | 什么时候看 |
|------|------------|-----------|
| **README.md**（本文） | 这是什么？怎么装、怎么用？接口有哪些？ | 第一次接触项目 |
| [TUTORIAL.md](TUTORIAL.md) | 代码**为什么**这么写？ | 想读懂 / 学会这个项目 |
| [STANDARDS.md](STANDARDS.md) | 改代码必须遵守哪些规矩？ | 准备动手改代码 |
| [ROADMAP.md](ROADMAP.md) | 接下来做什么？ | 想了解演进方向 |

> 四份文档各司其职，**同一份知识只在一个地方讲**：本文只讲"怎么用"，原理与设计取舍在 TUTORIAL，规范与格式要求（依赖、代码风格、测试要求、提交格式）在 STANDARDS，版本规划在 ROADMAP。

---

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

技术栈：Python 3.10+（标准库为主）、Flask ≥ 2.3（仅 Web 端需要）、原生 HTML/CSS/JS、SQLite。

## 快速开始

```bash
# 1. 确认 Python 版本（需要 3.10+）
python --version

# 2. 安装依赖（运行只需 Flask；改代码再加 requirements-dev.txt）
python -m pip install -r requirements.txt

# 3. 启动命令行版
python run_cli.py

# 4. 启动网页版（浏览器打开 http://127.0.0.1:5000）
python run_web.py
```

首次运行会在项目根目录自动创建 SQLite 数据库 `questions.db`（首次写入时建表）。

### 三种启动方式（等价，按需选）

代码采用 **src 布局**，因此未安装时不能直接 `python -m question_notebook`：

| 方式 | 命令 | 前提 |
|------|------|------|
| **① 启动脚本**（推荐） | `python run_cli.py` / `python run_web.py` | 只需装 Flask |
| **② 模块方式** | `python -m src.question_notebook` / `python -m src.question_notebook.web` | 无需安装 |
| **③ 控制台命令** | `question-notebook` / `question-notebook-web` | 需先 `python -m pip install -e .` |

三种方式最终都调用同一个函数（CLI 为 `question_notebook.cli.main`，Web 为 `question_notebook.web.main`），行为完全一致。原因见 [TUTORIAL.md 第 0.5 节](TUTORIAL.md#05-看懂新结构什么是包python-又怎么找到代码)。

### 启用密码认证（可选）

Web 版默认**免登录**（仅适合本机 `127.0.0.1` 使用）。若要在局域网/公网部署，请设置密码：

```bash
# Linux / macOS
QUESTION_NOTEBOOK_PASSWORD=你的密码 python run_web.py

# Windows (PowerShell)
$env:QUESTION_NOTEBOOK_PASSWORD="你的密码"; python run_web.py
```

| 环境变量 | 说明 |
|---------|------|
| `QUESTION_NOTEBOOK_PASSWORD` | 登录密码。设置后启用登录页，未设置则免登录 |
| `QUESTION_NOTEBOOK_SECRET` | 可选，Flask 会话签名密钥；不设置则首次运行自动生成 `.flask_secret` 持久化保存 |
| `QUESTION_NOTEBOOK_DATA_DIR` | 可选，数据目录位置，见下节 |

### 从旧版 JSON 迁移（可选）

```bash
python scripts/migrate_to_sqlite.py             # 执行迁移
python scripts/migrate_to_sqlite.py --dry-run   # 仅预览，不写库
python scripts/migrate_to_sqlite.py --force     # 覆盖已存在的 questions.db（先备份）
```

迁移会：备份原 JSON 到 `backups/` → 应用包内 `schema.sql` 建表 → 单事务导入数据 → 读回校验。原有 ID 完整保留。

## 使用说明

**CLI**：启动后是菜单式交互（`1` 查看 / `2` 添加 / `3` 标记解决 / `4` 删除 / `5` 搜索 / `6` 编辑 / `7` 备份与恢复 / `8` 状态筛选 / `9` 导出 CSV / `10` 分类查看 / `0` 退出）。

**Web**：问题卡片列表 + 实时搜索 + 状态与分类组合筛选，增删改均弹窗交互；可折叠的「数据可视化」面板展开即绘制分类分布柱状图与解决率环形图。

**备份与恢复**：备份文件存于 `backups/`，命名格式 `questions_YYYYMMDD_HHMMSS_微秒.db`；恢复会覆盖当前全部数据，执行前有二次确认，且含路径穿越防护。

## 数据存储

数据默认存储于**项目根目录**的 SQLite 数据库 `questions.db`，单文件、零配置；表结构定义在 [src/question_notebook/schema.sql](src/question_notebook/schema.sql)。

数据与密钥的位置由 `paths.py` 统一决定，可用环境变量整体改写：

```bash
# 把数据放到项目外的独立目录（例如部署到服务器时）
# Windows PowerShell
$env:QUESTION_NOTEBOOK_DATA_DIR="D:\qn-data"; python run_cli.py
# Linux / macOS
QUESTION_NOTEBOOK_DATA_DIR=/var/lib/question-notebook python run_cli.py
```

`questions.db`、`backups/`、`exports/`、`.flask_secret`、`.auth_salt` 都基于该目录。**为什么代码在 `src/` 而数据在根目录**，以及非可编辑安装时必须设置该变量——见 [TUTORIAL.md 第 1.8 节](TUTORIAL.md#18-路径从哪来pathspy-与不能把数据写进代码目录)。表结构与字段含义见 [TUTORIAL.md 第 1.3 节](TUTORIAL.md#13-表结构数据在数据库里长什么样)。

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

项目内置 **37 个自动化测试**（数据层 12 + CLI 6 + Web 19），两种运行方式结果一致：

```bash
python tests/test_question_notebook.py   # 推荐日常用：零依赖，只需 Python 标准库
pytest                                   # 装了 pytest 后可用：支持 -k 筛选、--lf 重跑失败项
```

测试文件会自己把 `src/` 加进模块搜索路径，因此**不需要安装任何东西**即可运行；测试数据写入项目内 `.tmp/`（已 gitignore），**绝不会读写你真实的 `questions.db`**。

改动代码的完整流程、测试要求与提交格式见 [STANDARDS.md](STANDARDS.md)。

## 项目结构

```
question_notebook/
├── run_cli.py                 # 启动入口：命令行版
├── run_web.py                 # 启动入口：网页版
├── conftest.py                # pytest 初始化：把 src/ 加进模块搜索路径
│
├── src/question_notebook/     # 【代码包】
│   ├── __init__.py            # 包说明 + 版本号 + 数据层 API 重导出（不加载 Flask）
│   ├── __main__.py            # python -m question_notebook → CLI
│   ├── paths.py               # 路径唯一来源（数据/密钥位置）
│   ├── models.py              # 数据层：Question 模型 + SQLite 读写 + 跨进程锁
│   ├── cli.py                 # CLI 界面层
│   ├── web.py                 # Web 界面层（Flask 路由 + 认证 + CSRF）
│   ├── schema.sql             # SQLite 表结构定义
│   └── templates/index.html   # Web 前端页面
│
├── tests/test_question_notebook.py   # 37 个自动化测试
├── scripts/
│   ├── check_deps.py          # 依赖声明一致性校验（CI 使用）
│   └── migrate_to_sqlite.py   # JSON → SQLite 一次性迁移脚本
│
├── pyproject.toml             # 依赖 + 控制台命令 + ruff/pytest/coverage 配置
├── requirements.txt           # 运行依赖（Flask）
├── requirements-dev.txt       # 开发依赖（ruff + pytest + coverage）
├── .github/workflows/ci.yml   # CI：ruff 检查 + 依赖校验 + 四版本测试矩阵
├── .editorconfig / .gitignore / .gitmessage
│
├── questions.db               # 你的数据（自动生成，不入版本库）
├── backups/  exports/  .tmp/  # 运行时目录（不入版本库）
└── README / TUTORIAL / STANDARDS / ROADMAP
```

模块职责与依赖关系图见 [TUTORIAL.md 第 4.1 节](TUTORIAL.md#41-为什么要分层)。

## 路线图

| 版本 | 主题 | 状态 |
|------|------|------|
| v0.1.0 | 个人工具（CLI + Web + 模块化） | ✅ 已发布 |
| v0.2.0 | 数据升级（SQLite 迁移） | ✅ 已完成 |
| v0.2.x | 数据可视化 + 工程规范化 | ✅ 已完成 |
| v0.3.0 | 标准化包结构（src 布局） | ✅ 已完成 |
| v0.3.x | 社区化（用户系统 + 问答） | 📋 规划中 |
| v0.4.0 | 社会问题采集（数据接入） | 📋 规划中 |
| v1.0.0 | 关联与发布（平台化） | 📋 规划中 |

完整规划与验收标准详见 [ROADMAP.md](ROADMAP.md)。

## 更新日志

### 2026-09-26 · v0.3.0 标准化包结构 + 文档瘦身

**目录结构（破坏性变更，旧路径已不存在）**
- 代码迁入 `src/question_notebook/` 包：`question_notebook.py` → `cli.py`、`web_app.py` → `web.py`，`models.py` / `schema.sql` / `templates/` 一并入包
- 测试迁入 `tests/test_question_notebook.py`；迁移脚本迁入 `scripts/`
- 新增 `paths.py` 作为路径唯一来源，实现**代码目录与数据目录分离**；`.flask_secret` / `.auth_salt` 移到数据目录
- 新增 `QUESTION_NOTEBOOK_DATA_DIR` 环境变量可整体改写数据位置

**启动方式**
- 新增 `run_cli.py` / `run_web.py`（未安装即可用）；注册控制台命令 `question-notebook` / `question-notebook-web`
- 三种方式最终调用同一个 `main()`，行为一致

**文档**
- 删除 `CODE_WIKI.md`：其内容与源码重复（重述常量/函数/路由），源码才是唯一不会过期的真相；其中确有价值的依赖关系图与模块职责表并入 [TUTORIAL.md](TUTORIAL.md)
- 本文瘦身：只保留"怎么用"，原理移入 TUTORIAL、规范移入 STANDARDS，消除同一主题在多份文档重复维护
- TUTORIAL 扩写包与导入、路径解析、导入报错排查等新手高频卡点，并新增 4 个动手练习

### 2026-09-26 · v0.2.2 工程规范化

- 新增 `pyproject.toml`、`requirements.txt` / `requirements-dev.txt`、`scripts/check_deps.py`
- 引入 ruff 静态检查与 pytest 测试运行器，新增 `.editorconfig`、`.gitmessage`
- 新增 GitHub Actions CI：ruff 检查 + Python 3.10/3.11/3.12/3.13 矩阵
- 新增 [STANDARDS.md](STANDARDS.md) 工程规范文档
- 修复测试数据落盘位置（由系统临时目录改为项目内 `.tmp/`），消除受限环境下的 `PermissionError`

> 更早版本（v0.1.0 ~ v0.2.1）的详细变更见 git 历史：`git log --oneline`
