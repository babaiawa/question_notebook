# Question Notebook · 代码 Wiki

> 本文档是 Question Notebook（问题笔记本）项目的**代码级知识库**，面向开发者/维护者，系统梳理项目架构、模块职责、关键类与函数、依赖关系与运行方式。
>
> 配套文档：[README.md](README.md)（项目说明）· [TUTORIAL.md](TUTORIAL.md)（教学讲解）· [ROADMAP.md](ROADMAP.md)（路线图）

---

## 目录

1. [项目概览](#1-项目概览)
2. [目录结构](#2-目录结构)
3. [整体架构](#3-整体架构)
4. [模块职责与依赖关系](#4-模块职责与依赖关系)
5. [关键类与函数详解](#5-关键类与函数详解)
6. [关键业务流程](#6-关键业务流程)
7. [数据存储格式](#7-数据存储格式)
8. [REST API 参考](#8-rest-api-参考)
9. [依赖清单](#9-依赖清单)
10. [运行方式](#10-运行方式)
11. [测试说明](#11-测试说明)

---

## 1. 项目概览

Question Notebook 是一个**轻量级个人问题记录与知识管理工具**，帮助用户记录学习/工作中遇到的问题、追踪解决进度、沉淀解决方案，支持分类管理、全文检索、备份恢复与 CSV 导出。

核心特征：

| 维度 | 说明 |
|------|------|
| 双端界面 | CLI 命令行 + Web 浏览器界面，共享同一数据层 |
| 分层架构 | 数据层（`models.py`）与界面层（CLI / Web）解耦 |
| 存储方式 | 本地 SQLite 数据库（`questions.db`），单文件零配置，事务保证一致性 |
| 技术栈 | Python 3.10+ 标准库 + Flask（仅 Web 端需要） |
| 测试 | 标准库 `unittest`，测试数据隔离到临时目录 |

---

## 2. 目录结构

```
question_notebook/
├── models.py              # 数据层：Question 模型 + SQLite 读写 + 跨进程锁
├── question_notebook.py   # CLI 界面层
├── web_app.py             # Web 界面层（Flask 路由 + 认证 + CSRF）
├── test_qn.py             # 自动化测试（数据层 + CLI 层 + Web 层）
├── templates/
│   └── index.html         # Web 前端页面（内嵌 CSS + JS + 登录页）
├── schema.sql             # SQLite 建表脚本（questions 表 + 索引 + schema_meta）
├── migrate_to_sqlite.py   # 一次性迁移脚本：questions.json → questions.db
├── questions.db           # SQLite 数据文件（首次写入时自动创建并建表）
├── .flask_secret          # Flask 会话签名密钥（首次运行自动生成）
├── .auth_salt             # 密码哈希盐（启用认证后自动生成）
├── backups/               # 备份目录（备份时自动创建）
├── exports/               # CSV 导出目录（导出时自动创建）
├── README.md              # 项目说明文档
├── TUTORIAL.md            # 教学文档
├── ROADMAP.md             # 路线图
├── CODE_WIKI.md           # 代码级知识库（本文档）
└── .gitignore             # Git 忽略规则
```

> 运行期动态生成的目录和文件（`backups/`、`exports/`、`.flask_secret`、`.auth_salt`、损坏文件的 `.bak`）不在版本控制中。

---

## 3. 整体架构

项目采用**分层模块化**设计，遵循单一职责原则，依赖方向自上而下单向流动：

```
┌──────────────────────────────────────────────────┐
│                    界面层（表现层）                │
│   ┌──────────────────┐    ┌──────────────────┐   │
│   │   CLI 命令行界面  │    │  Web 界面 (Flask) │   │
│   │ question_        │    │  web_app.py      │   │
│   │ notebook.py      │    │  + templates/    │   │
│   │                  │    │    index.html    │   │
│   └────────┬─────────┘    └────────┬─────────┘   │
└────────────┼───────────────────────┼─────────────┘
             │        调用            │
┌────────────▼───────────────────────▼─────────────┐
│                  数据层（models.py）              │
│   Question 模型 · to_dict/from_dict 序列化        │
│   load_questions / save_questions SQLite 读写     │
│   （含损坏自动备份 .bak、建表幂等、单事务写入）       │
└──────────────────────────────────────────────────┘
```

**三条设计原则：**

1. **单一职责**：数据层只负责"数据长什么样、怎么存取"；界面层只负责输入输出、菜单、路由。
2. **依赖单向**：界面层依赖数据层，数据层不依赖任何界面实现。
3. **存储隔离**：文件读写集中在 `models.py`，未来迁移到 SQLite/PostgreSQL 时界面层零改动。

**分层带来的收益：** CLI 与 Web 共享同一份数据逻辑，改 bug 只改一处；同一份 `questions.db` 在两个界面间数据完全互通。

---

## 4. 模块职责与依赖关系

### 4.1 模块职责一览

| 模块 | 层级 | 职责 |
|------|------|------|
| `models.py` | 数据层 | 定义 `Question` 模型、序列化/反序列化、SQLite 读写、跨进程写锁、路径常量 |
| `question_notebook.py` | 界面层（CLI） | 命令行菜单循环、交互式增删改查、备份恢复、CSV 导出、分类浏览 |
| `web_app.py` | 界面层（Web） | Flask 应用、REST 路由、密码认证、CSRF 防护、HTTP 请求校验与响应、导出/备份/恢复接口 |
| `templates/index.html` | 界面层（前端） | 浏览器渲染、登录页、`fetch` 调用 API、搜索筛选、模态框交互 |
| `test_qn.py` | 测试层 | 数据层、CLI 层与 Web 层（含认证与 CSRF）的自动化测试，测试数据隔离 |

### 4.2 依赖关系图

```
test_qn.py ──────────► models.py
     │                      ▲
     └────────► question_notebook.py ──► models.py
                                         ▲
web_app.py ─────────────────────────────┘
     ▲
     └────────► templates/index.html（通过 HTTP/fetch 间接调用）
```

关键依赖说明：

- `question_notebook.py` 与 `web_app.py` 都通过 `from models import ...` 复用数据层。
- `test_qn.py` 同时导入 `models` 与 `question_notebook as cli` 进行测试。
- 前端 `index.html` 不直接 import 后端，而是通过 `fetch` 调用 `web_app.py` 暴露的 REST API。

### 4.3 导入关系（符号级）

`models.py` 导出的符号：

| 符号 | 类型 | 被谁使用 |
|------|------|---------|
| `Question` | 类 | CLI、Web、测试 |
| `load_questions` | 函数 | CLI、Web、测试 |
| `save_questions` | 函数 | CLI、Web、测试 |
| `backup_data` | 函数 | CLI、Web、测试 |
| `list_backups` | 函数 | CLI、Web、测试 |
| `restore_data` | 函数 | CLI、Web、测试 |
| `build_csv` | 函数 | CLI、Web、测试 |
| `data_lock` | 上下文管理器 | CLI、Web（写事务加锁） |
| `DATA_FILE` | 常量 | CLI、Web、测试 |
| `BACKUP_DIR` | 常量 | CLI、测试 |
| `EXPORT_DIR` | 常量 | CLI、测试 |
| `DEFAULT_CATEGORY` | 常量 | CLI、Web、测试 |

> ⚠️ **值拷贝陷阱**：CLI/Web 用 `from models import DATA_FILE` 拿到的是字符串值拷贝，而非引用。测试重定向数据路径时，必须**同时**更新 `models.DATA_FILE` 与 `cli.DATA_FILE`（含 `BASE_DIR`，见 `test_qn.py` 的 `setUp`）。

---

## 5. 关键类与函数详解

### 5.1 models.py（数据层）

#### 常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `BASE_DIR` | `os.path.dirname(os.path.abspath(__file__))` | 脚本所在目录，用于定位数据文件 |
| `DATA_FILE` | `BASE_DIR/questions.db` | SQLite 数据库文件路径 |
| `BACKUP_DIR` | `BASE_DIR/backups` | 备份目录路径 |
| `EXPORT_DIR` | `BASE_DIR/exports` | CSV 导出目录路径 |
| `DEFAULT_CATEGORY` | `"未分类"` | 默认分类 |
| `BACKUP_NAME_PATTERN` | `^questions_\d{8}_\d{6}(_\d{6})?\.db$` | 备份文件名白名单（恢复接口校验用） |

> 路径基于脚本文件目录定位，因此**从任意工作目录运行都能正确找到数据文件**。

#### 类 `Question`

问题数据模型，封装一条问题的全部属性。

```python
class Question:
    def __init__(self, title, description="", is_solved=False,
                 solution="", category=DEFAULT_CATEGORY):
```

| 属性 | 类型 | 说明 |
|------|------|------|
| `id` | int \| None | 唯一编号，`None` 表示尚未分配，`save_questions` 时自动分配 |
| `title` | str | 标题（必填） |
| `description` | str | 详细描述，可为空 |
| `timestamp` | str | 创建时间，`YYYY-MM-DD HH:MM:SS`，构造时自动生成 |
| `is_solved` | bool | 解决状态 |
| `solution` | str | 解决方案，未解决时为空 |
| `category` | str | 分类，默认 `未分类` |

方法：

| 方法 | 类型 | 说明 |
|------|------|------|
| `to_dict()` | 实例方法 | 对象 → 字典（序列化），返回全部 7 个字段 |
| `from_dict(item)` | `@classmethod` | 字典 → 对象（反序列化），用 `item.get(key, default)` 兼容旧数据缺字段 |

> `from_dict` 用 `.get()` 带默认值，而非 `item['key']`，保证历史数据缺失 `category` 等字段时不会抛出 `KeyError`，自动补默认值。

#### 函数 `load_questions()`

```python
def load_questions():
```

从 `DATA_FILE`（SQLite）加载问题列表，返回 `list[Question]`。容错逻辑：

1. `DATA_FILE` 不存在 → 返回空列表 `[]`。
2. `_connect()` 抛 `sqlite3.DatabaseError`（文件不是有效 SQLite 库）→ 调用 `_handle_corrupt_db()` 重命名为 `questions.db.bak` 后返回空列表，**不崩溃**。
3. `_ensure_schema(conn)` 幂等建表（`IF NOT EXISTS`）。
4. `SELECT ... FROM questions ORDER BY id` 逐行经 `_row_to_question` 转换；查询过程抛 `DatabaseError` 同样走 `_handle_corrupt_db()`。
5. `finally` 关闭连接。

#### 函数 `save_questions(questions)`

```python
def save_questions(questions):
```

将问题列表写入 `DATA_FILE`（SQLite）。行为：

- 先扫描已有最大 `id`，对 `id is None` 的新对象自增分配 ID（与旧版一致）。
- `_connect()` → `_ensure_schema()` 建表幂等。
- **单事务写入**：`BEGIN` → `DELETE FROM questions` → `executemany(INSERT ...)` → `commit()`，一次性清空并重写全表。
- 任何异常 → `rollback()` 后 `raise`；`finally` 关闭连接。
- 不再使用临时文件 + `os.replace`，事务本身保证写入原子性。

#### 数据操作函数（备份/恢复/导出，CLI 与 Web 共用）

| 函数 | 说明 |
|------|------|
| `backup_data()` | 复制 `DATA_FILE` 到 `BACKUP_DIR`，文件名 `questions_YYYYMMDD_HHMMSS_微秒.db`（微秒避免同秒覆盖），返回文件名；无数据文件返回 `None` |
| `list_backups()` | 列出全部备份文件名（新的在前），仅认符合 `BACKUP_NAME_PATTERN` 的文件 |
| `restore_data(filename)` | 从备份恢复：正则白名单校验文件名（拒绝路径穿越与不合规命名），读取备份 `.db` 后经 `tempfile.mkstemp(dir=BASE_DIR, suffix=".tmp")` + `os.replace` 原子替换 `DATA_FILE`，成功返回 `True` |
| `build_csv(questions)` | 生成 CSV 内容字符串（含 `\ufeff` BOM 头），由调用方负责写文件/下载 |

#### 连接与建表辅助函数

| 函数 | 说明 |
|------|------|
| `_connect()` | `sqlite3.connect(DATA_FILE, timeout=5.0)`，设置 `row_factory=Row`、`PRAGMA foreign_keys=ON` |
| `_ensure_schema(conn)` | 执行内联 `_SCHEMA_SQL`（`CREATE TABLE IF NOT EXISTS` + 3 个索引），幂等 |
| `_row_to_question(row)` | 将 `sqlite3.Row` 转为 `Question`，`is_solved` 经 `bool(row["is_solved"])` 还原 |
| `_handle_corrupt_db()` | 文件不是有效 SQLite 库时重命名为 `DATA_FILE + ".bak"`，打印告警并返回 `[]` |

> `_SCHEMA_SQL` 在 `models.py` 内联定义，等价于仓库根目录 `schema.sql` 的 `questions` 表与索引部分（`schema.sql` 额外含 `schema_meta` 表，记录 `schema_version` 与 `migrated_at`，仅供迁移脚本 `migrate_to_sqlite.py` 使用）。

#### 跨进程锁 `data_lock()`

基于文件锁的上下文管理器（`@contextlib.contextmanager`），保护"读-改-写"事务：

- Windows 用 `msvcrt.locking`，Linux/macOS 用 `fcntl.flock` 独占锁。
- 锁文件为 `BASE_DIR/.data.lock`，锁放在调用方事务层（如 `with data_lock():` 包住整段读-改-写），`save_questions` 等函数内部不再加锁，避免同进程重入死锁。
- 使 CLI 与 Web 同时运行、多进程/多 worker 部署时写操作同样串行安全，避免 SQLite 在并发写时抛 `database is locked`。

---

### 5.2 question_notebook.py（CLI 界面层）

> **并发安全**：CLI 与 Web 共享同一份数据文件。CLI 的每个写操作（添加/解决/删除/编辑/恢复）都在 `data_lock()` 内基于**磁盘最新数据**重做，避免覆盖 Web 端刚写入的内容；读操作（查看/搜索/筛选/分类/导出）先调用 `_refresh(questions)` 从磁盘重载，保证看到 Web 端的最新改动。

#### `_refresh(questions)`

读操作前刷新内存快照：`questions.clear()` 后 `extend(load_questions())`，从磁盘重新加载，反映 Web 端最新改动。SQLite 事务保证每次写入都是一致快照，因此读无需加锁。

#### `print_questions(questions, header, empty_msg=...)`

格式化打印问题列表，被「查看全部」「筛选」「分类查看」三处复用。逐条输出 `[id] 标题 | 分类 | 状态 | 时间`，并可选输出描述与解决方案。

#### `add_question(questions)`

交互式添加新问题。标题为空或全空格时取消；分类为空时回退 `DEFAULT_CATEGORY`。输入在锁外完成，锁内重新 `load_questions()` 后追加并 `save_questions`，再同步内存快照。

#### `list_questions(questions)`

输出全部问题（委托给 `print_questions`）。

#### `solve_question(questions)`

按 ID 标记问题为已解决并记录解决方案。ID 非数字、找不到、已是已解决状态均给出提示并返回。

#### `delete_question(questions)`

按 ID 删除问题，含**二次确认**（`y/N`，默认取消）。用列表推导式原地过滤：

```python
questions[:] = [q for q in questions if q.id != q_id]
```

> 使用 `questions[:] = ...` 是原地修改，保证持有该列表引用的外部代码看到新内容。

#### `search_questions(questions)`

多关键词搜索。忽略大小写，匹配标题/描述/方案/分类，AND 逻辑（`all(...)` 全部命中）。

#### `edit_question(questions)`

按 ID 编辑问题，可修改标题/描述/分类/解决方案，**回车留空表示该项保持不变**（部分更新）。

#### `filter_questions(questions)`

按解决状态筛选（只看未解决 / 只看已解决）。

#### `backup_questions()`

委托数据层 `backup_data()` 创建带时间戳（含微秒）的备份，打印备份路径。

#### `restore_questions(questions)`

列出备份文件（数据层 `list_backups()`），选择编号后二次确认，数据层 `restore_data()` 执行恢复（含白名单校验），成功后 `clear() + extend(load_questions())` 重新加载到内存。

#### `backup_menu(questions)`

备份与恢复的子菜单循环（备份 / 恢复 / 返回）。

#### `export_csv(questions)`

将问题列表导出为 CSV 到 `EXPORT_DIR`。内容由数据层 `build_csv()` 生成（含 BOM 头），界面层只负责写文件，Excel 打开不乱码。

#### `view_by_category(questions)`

按分类浏览：收集去重分类、显示各分类数量、选择后打印该分类下问题。

#### `main()`

程序入口。加载数据 → 打印主菜单 → 死循环分发选项（`0` 退出）。

---

### 5.3 web_app.py（Web 界面层）

#### 安全配置（启动时）

```python
app = Flask(__name__)
app.json.ensure_ascii = False  # 中文原样输出，不做 \uXXXX 转义
```

- **会话密钥**：优先取环境变量 `QUESTION_NOTEBOOK_SECRET`；否则首次运行生成随机密钥并持久化到 `.flask_secret`（重启后登录会话仍有效）。
- **密码认证**：`QUESTION_NOTEBOOK_PASSWORD` 环境变量设置后启用（`AUTH_ENABLED=True`）。密码不存明文，用 `hashlib.pbkdf2_hmac("sha256", password, salt, 100_000)` 生成哈希，盐持久化到 `.auth_salt`。
- **CSRF**：会话级 token（`secrets.token_urlsafe(32)`），通过 `X-CSRF-Token` 请求头校验。

**`_password_verify(password)`**：用 PBKDF2 重算哈希并与存储哈希 `hmac.compare_digest` 比较，防时序攻击。未启用认证时直接返回 `True`。

**`_require_auth(view_func)`**：装饰器，认证开启且 `session` 未登录时返回 `401 {"error": "未登录"}`。

**`_ensure_csrf_token()`**：获取当前会话的 CSRF token，不存在则生成并写入 `session`。

**`_csrf_protection()`**：`@app.before_request` 钩子，对所有非 `GET/HEAD/OPTIONS` 请求校验 `X-CSRF-Token`（与 session 中 token 做 `hmac.compare_digest`），不匹配返回 `403`；`POST /api/login` 豁免（登录前无 session）。

**`_get_json_body()`**：封装 `request.get_json(force=True, silent=True)`，且**仅接受 dict**（数组/字符串等非对象返回 `None`），由调用方返回 `400`，避免框架抛出 500 或 `.get()` 崩溃。

**写操作锁**：由数据层跨进程文件锁 `data_lock()` 提供（不再是进程内 `threading.Lock`）。`api_add` / `api_update` / `api_delete` / `api_backup` / `api_restore` 均以 `with data_lock():` 串行化整段"读-改-写"。

#### 路由与处理函数

| 路由函数 | 方法与路径 | 说明 |
|---------|-----------|------|
| `index()` | `GET /` | 渲染 `templates/index.html`，注入 csrf_token / auth_enabled / logged_in |
| `api_auth_status()` | `GET /api/auth-status` | 返回 `{auth_enabled, logged_in}` |
| `api_csrf()` | `GET /api/csrf` | 下发当前会话的 CSRF token |
| `api_login()` | `POST /api/login` | 校验密码，写入 `session`，返回新 CSRF token |
| `api_logout()` | `POST /api/logout` | 清空 `session` |
| `api_list()` | `GET /api/questions` | 返回全部问题（`@_require_auth`） |
| `api_add()` | `POST /api/questions` | 添加问题；`title` 空或请求体非对象返回 400 |
| `api_update(qid)` | `PUT /api/questions/<int:qid>` | 部分更新（含标记解决），`is_solved` 严格布尔校验，不存在返回 404 |
| `api_delete(qid)` | `DELETE /api/questions/<int:qid>` | 删除问题，不存在返回 404 |
| `api_export()` | `GET /api/export` | 导出 CSV 附件下载（`build_csv` 生成，含 BOM） |
| `api_backup()` | `POST /api/backup` | 创建带时间戳备份快照（数据层 `backup_data`） |
| `api_backups()` | `GET /api/backups` | 列出备份文件（数据层 `list_backups`） |
| `api_restore()` | `POST /api/restore` | 从备份恢复（数据层 `restore_data`，文件名白名单校验） |

#### 入口

```python
if __name__ == "__main__":
    app.run(debug=False, host='127.0.0.1', port=5000)
```

---

### 5.4 templates/index.html（前端）

前端为单页应用，内嵌 CSS 与原生 JavaScript，通过 `fetch` 调用后端 API。含登录页，`fetch` 统一封装携带 CSRF 头并处理 401。

#### 全局状态

| 变量 | 说明 |
|------|------|
| `AUTH_ENABLED` | 后端注入的认证开关（`"true"/"false"`） |
| `__csrf_token` | CSRF token（后端模板注入，登录成功后刷新） |
| `questions` | 从后端拉取的全部问题 |
| `selectedBackup` | 恢复弹窗中选中的备份文件名 |
| `editingId` | 正在编辑的问题 ID（`null` 表示新增） |
| `solvingId` | 正在标记解决的问题 ID |
| `deletingId` | 待删除的问题 ID |

#### 关键函数

| 函数 | 说明 |
|------|------|
| `api(url, opts)` | `fetch` 封装：自动带 `X-CSRF-Token` 头，遇 401 跳登录页，处理 CSRF/业务错误 |
| `showLoginPage()` / `hideLoginPage()` | 登录页显隐 |
| `doLogin()` / `doLogout()` | 登录（成功后刷新 token）/ 登出 |
| `esc(s)` | HTML 转义，防 XSS/破坏页面结构 |
| `toast(msg)` | 底部轻提示 |
| `openModal(id)` / `closeModal(id)` | 模态框显隐 |
| `load()` | 拉取 `/api/questions` 并渲染 |
| `renderFilters()` | 动态生成分类下拉（去重） |
| `currentFilter()` | 读取搜索词 + 状态 + 分类筛选条件 |
| `render()` | 核心渲染：过滤 + 统计条 + 卡片列表 |
| `openAddModal()` / `openEditModal(id)` / `saveEdit()` | 添加/编辑流程 |
| `openSolveModal(id)` / `saveSolve()` | 标记解决流程 |
| `openDeleteModal(id)` / `confirmDelete()` | 删除流程 |
| `exportCsv()` / `doBackup()` / `openRestoreModal()` / `pickBackup()` / `confirmRestore()` | 导出/备份/恢复流程 |

**过滤逻辑（`render`）：** 状态筛选 + 分类筛选 + 多关键词（空格分隔，全部命中 AND），三条件叠加。

---

### 5.5 test_qn.py（测试层）

使用标准库 `unittest`，`setUp` 将数据路径重定向到临时目录（`tempfile.mkdtemp`），`tearDown` 清理，保证不污染真实数据。

#### `TestModels(unittest.TestCase)` — 数据层测试

| 用例 | 覆盖点 |
|------|--------|
| `test_question_roundtrip` | 序列化/反序列化往返一致 |
| `test_save_load_roundtrip` | 保存后加载一致 + ID 自动分配 |
| `test_schema_defaults` | 直接向 SQLite 仅写 id/title/timestamp，验证 DEFAULT 自动补 `category`/`description`/`solution`/`is_solved` |
| `test_corrupt_db` | 写入损坏内容到 `.db` 路径，验证 `.bak` 生成且返回 `[]` |
| `test_non_db_file_treated_as_corrupt` | 将 `{"a":1}`、`"just a string"`、`123` 写入 `.db` 路径均按损坏处理 |
| `test_atomic_save` | 单事务写入无 `.tmp` 残留，数据完整 |
| `test_db_file_is_valid_sqlite` | 校验 SQLite 魔数头 `SQLite format 3` 且可查询表 |
| `test_backup_name_unique_and_filtered` | 备份文件名含微秒不覆盖；`list_backups` 过滤不合规文件 |
| `test_restore_rejects_bad_names` | `restore_data` 拒绝路径穿越/前缀不符文件名 |
| `test_build_csv` | CSV 生成含 BOM 头、表头、数据行 |

#### `TestCLI(unittest.TestCase)` — CLI 层测试

| 用例 | 覆盖点 |
|------|--------|
| `test_full_flow` | 增→改→解决→删除 全链路 |
| `test_export_csv` | CSV 导出 + BOM 校验 |
| `test_backup_restore` | 备份→删除→恢复往返 |
| `test_view_by_category` | 分类浏览（正常 + 无效编号） |
| `test_multi_keyword_search` | 多关键词 AND 搜索 |
| `test_refresh_syncs_from_disk` | `_refresh` 从磁盘同步 Web 端写入的最新数据 |

#### `TestWeb(unittest.TestCase)` — Web 层测试（Flask test_client，含认证与 CSRF）

用 `HAS_FLASK` 标志跳过（未装 Flask 时不影响数据层/CLI 测试）。`setUp` 用 test_client 建立会话并取 CSRF token，通过 `_csrf_json` / `_csrf_put_json` / `_csrf_delete` 辅助方法在请求里带 `X-CSRF-Token` 头。

| 类别 | 用例 | 覆盖点 |
|------|------|--------|
| 业务 | `test_crud_flow` | 增删改查全链路 |
| 业务 | `test_bad_bodies` / `test_empty_title` / `test_is_solved_type_check` / `test_not_found` | 空 body、非法 JSON、空标题、布尔类型校验、404 |
| 业务 | `test_export_csv` / `test_backup_restore_flow` / `test_restore_rejects_bad_names` / `test_backups_empty` | 导出、备份恢复、文件名白名单 |
| CSRF | `test_csrf_required_for_post` / `test_csrf_required_for_put_delete` / `test_csrf_wrong_token_rejected` | 缺失/错误 CSRF 头返回 403 |
| CSRF | `test_login_endpoint_exempt_from_csrf` / `test_csrf_token_issued` | 登录接口 CSRF 豁免、token 发放 |
| 认证 | `test_auth_disabled_by_default` | 默认免登录 |
| 认证 | `test_auth_enabled_requires_login` / `test_logout_clears_session` / `test_login_empty_body_is_400` | 登录成功/失败、登出失效、非法 body |

### 5.6 migrate_to_sqlite.py（一次性迁移脚本）

将历史 `questions.json` 迁移到 `questions.db` 的命令行脚本，迁移完成后旧库即用 SQLite 替代。行为：

- 先把原始 `questions.json` 备份到 `backups/`。
- 应用 `schema.sql` 建表（含 `questions` 表 + 索引 + `schema_meta`，写入 `schema_version`、`migrated_at`）。
- 在**单事务**内 `INSERT` 全部问题，**保留原始 ID** 不重新分配。
- 迁移后回读校验数据一致性。
- 支持 `--dry-run`（只打印计划不落盘）与 `--force`（目标已存在时覆盖）。

> 该脚本只在从 JSON 时代升级到 SQLite 时运行一次，正常运行不再需要。

---

## 6. 关键业务流程

### 6.1 添加问题（Web 端全链路）

```
前端 saveEdit()  (fetch POST /api/questions)
      │  body: {title, description, category}
      ▼
后端 api_add()   (web_app.py)
      │  CSRF 校验（before_request）→ 认证校验（@_require_auth）
      │  _get_json_body() 解析（空/非对象 → 400）
      │  校验 title 非空 → 构造 Question
      │  with data_lock():  (跨进程并发写串行化)
      ▼
数据层 save_questions() (models.py)
      │  分配 ID → 单事务：BEGIN → DELETE FROM questions → executemany INSERT → commit
      ▼
返回 201 + q.to_dict() → 前端 load() 重新渲染
```

### 6.2 损坏文件容错流程（数据层）

```
load_questions()
      │  DATA_FILE 不存在？
      ├─ 是 → 返回 []
      │  文件存在 → _connect() 打开 SQLite
      │        ├─ 成功且为有效 SQLite 库 → _ensure_schema → SELECT 返回
      │        └─ DatabaseError（不是有效 SQLite 库）→ 重命名 .bak → 返回 []
```

### 6.3 备份与恢复流程

```
备份：backup_data() → copy2(DATA_FILE → backups/questions_时间戳_微秒.db)
恢复：list_backups() 列出 → 选择备份 → 二次确认
     → restore_data() 白名单校验文件名 → 读取备份 .db
     → tempfile.mkstemp + os.replace 原子替换 DATA_FILE → 重新 load_questions()
```

---

## 7. 数据存储格式

数据存储在项目根目录的 SQLite 数据库文件 `questions.db`，单文件零配置。表结构由 `models.py` 内联的 `_SCHEMA_SQL`（与仓库根目录 `schema.sql` 的 `questions` 表+索引部分一致）定义：

```sql
CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY,
    title       TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    timestamp   TEXT    NOT NULL,
    is_solved   INTEGER NOT NULL DEFAULT 0 CHECK(is_solved IN (0,1)),
    solution    TEXT    NOT NULL DEFAULT '',
    category    TEXT    NOT NULL DEFAULT '未分类'
);
CREATE INDEX IF NOT EXISTS idx_questions_category  ON questions(category);
CREATE INDEX IF NOT EXISTS idx_questions_is_solved ON questions(is_solved);
CREATE INDEX IF NOT EXISTS idx_questions_timestamp ON questions(timestamp);
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER PRIMARY KEY | 唯一标识，`save_questions` 扫描最大值后自增分配 |
| `title` | TEXT NOT NULL | 标题，必填 |
| `description` | TEXT NOT NULL DEFAULT '' | 描述，缺省空字符串 |
| `timestamp` | TEXT NOT NULL | 创建时间 `YYYY-MM-DD HH:MM:SS` |
| `is_solved` | INTEGER NOT NULL DEFAULT 0 | 解决状态，`CHECK(is_solved IN (0,1))`，存 0/1，读取时 `bool()` 还原 |
| `solution` | TEXT NOT NULL DEFAULT '' | 解决方案，未解决时为空字符串 |
| `category` | TEXT NOT NULL DEFAULT '未分类' | 分类，缺省 `未分类` |

> `schema.sql` 另含 `schema_meta` 表（`schema_version`、`migrated_at`），仅由一次性迁移脚本 `migrate_to_sqlite.py` 写入。

> **容错**：建表语句幂等（`IF NOT EXISTS`）；若 `questions.db` 不是有效 SQLite 库，加载时自动重命名为 `questions.db.bak` 后重建，**不崩溃**。

---

## 8. REST API 参考

所有接口返回 JSON（`ensure_ascii=False`，中文原样输出）。

| 方法 | 路径 | 功能 | 请求体 | 成功状态码 |
|------|------|------|--------|-----------|
| GET | `/` | 渲染 Web 界面 | - | 200 |
| GET | `/api/auth-status` | 查询认证状态 | - | 200 |
| GET | `/api/csrf` | 下发 CSRF Token | - | 200 |
| POST | `/api/login` | 登录（校验密码） | `{password}` | 200 |
| POST | `/api/logout` | 登出 | - | 200 |
| GET | `/api/questions` | 获取全部问题 | - | 200 |
| POST | `/api/questions` | 添加问题 | `{title, description, category}` | 201 |
| PUT | `/api/questions/<id>` | 编辑问题（部分更新） | `{title?, description?, category?, is_solved?, solution?}` | 200 |
| DELETE | `/api/questions/<id>` | 删除问题 | - | 200 |
| GET | `/api/export` | 导出 CSV（附件） | - | 200 |
| POST | `/api/backup` | 创建备份快照 | - | 200 |
| GET | `/api/backups` | 列出备份文件 | - | 200 |
| POST | `/api/restore` | 从备份恢复 | `{filename}` | 200 |

**约定与错误处理：**

- 请求体为空或非 JSON 对象 → `400 {"error": "请求体必须是 JSON"}`（所有带 body 的接口）
- 添加问题 `title` 为空 → `400 {"error": "标题不能为空"}`
- `is_solved` 非布尔（如字符串 `"false"`）→ `400 {"error": "is_solved 必须是布尔值"}`
- 编辑/删除不存在的 ID → `404 {"error": "未找到该问题"}`
- 恢复接口文件名须匹配白名单 `questions_YYYYMMDD_HHMMSS[_微秒].db`（拒绝路径穿越与不合规命名）→ `400`；文件不存在 → `404`
- 编辑接口只更新请求体中出现的字段（部分更新语义）
- **CSRF**：除 `GET/HEAD/OPTIONS` 外的请求须带 `X-CSRF-Token` 头（值来自 `/api/csrf` 或页面模板注入），否则 `403 {"error": "CSRF 校验失败"}`；`POST /api/login` 豁免
- **认证**：启用密码后，未登录访问受保护接口 → `401 {"error": "未登录"}`；登录密码错误 → `401 {"error": "密码错误"}`

---

## 9. 依赖清单

### 9.1 运行时依赖

| 依赖 | 版本 | 用途 | 所属模块 |
|------|------|------|---------|
| Python | 3.10+ | 运行环境 | 全部 |
| Flask | 3.x | Web 框架（仅 Web 端需要） | `web_app.py` |

标准库（无需额外安装）：

| 模块 | 用途 | 所属模块 |
|------|------|---------|
| `sqlite3` | SQLite 数据库连接与事务 | `models.py` |
| `os` | 路径与文件系统操作 | 全部 |
| `re` | 备份文件名白名单正则 | `models.py` |
| `csv` / `io` | CSV 生成与字节流 | `models.py`、`web_app.py` |
| `datetime` | 时间戳生成 | `models.py`、`web_app.py` |
| `shutil` | 文件复制（备份） | `models.py` |
| `tempfile` | 恢复时原子替换的临时文件 | `models.py` |
| `contextlib` | `data_lock` 上下文管理器 | `models.py` |
| `fcntl` / `msvcrt` | 跨进程文件锁（Linux/macOS 用 fcntl，Windows 用 msvcrt） | `models.py` |
| `hashlib` | PBKDF2 密码哈希 | `web_app.py` |
| `hmac` | 防时序攻击的常量时间比较 | `web_app.py` |
| `secrets` | 会话密钥与 CSRF token 生成 | `web_app.py` |

### 9.2 测试依赖

| 模块 | 用途 |
|------|------|
| `unittest` | 测试框架 |
| `unittest.mock.patch` | 模拟 `input()` 输入 |
| `tempfile` | 临时目录隔离测试数据 |
| `sys` | 路径注入 |

> 项目无 `requirements.txt`，唯一需要手动安装的第三方依赖是 Flask：`pip install flask`。

---

## 10. 运行方式

### 10.1 环境准备

```bash
# 要求 Python 3.10+
python --version

# Web 版需安装 Flask
pip install flask
```

### 10.2 启动 CLI

```bash
python question_notebook.py
```

### 10.3 启动 Web

```bash
python web_app.py
```

启动后浏览器访问 **http://127.0.0.1:5000**。

**启用密码认证（可选）**：局域网/公网部署时设置密码，否则免登录（仅限本机）：

```bash
# Linux / macOS
QUESTION_NOTEBOOK_PASSWORD=你的密码 python web_app.py

# Windows (PowerShell)
$env:QUESTION_NOTEBOOK_PASSWORD="你的密码"; python web_app.py
```

可选环境变量：`QUESTION_NOTEBOOK_SECRET` 指定 Flask 会话签名密钥（不设则自动生成 `.flask_secret` 持久化）。

### 10.4 运行测试

```bash
python test_qn.py
```

### 10.5 首次运行行为

- 数据库 `questions.db` 首次写入时自动创建（`_ensure_schema` 幂等建表）。
- 备份目录 `backups/`、导出目录 `exports/` 在相应操作时自动创建。
- `.flask_secret`（会话密钥）首次运行自动生成；`.auth_salt`（密码盐）启用认证后自动生成。

---

## 11. 测试说明

- **入口**：`python test_qn.py`（`unittest` 默认发现并运行全部用例，`verbosity=2`）。
- **测试隔离**：`setUp` 将 `models` 与 `cli` 的 `BASE_DIR`/`DATA_FILE`/`BACKUP_DIR`/`EXPORT_DIR` 重定向到临时目录（`tempfile.mkdtemp`，其中 `models.DATA_FILE = os.path.join(tmpdir, "questions.db")`），`tearDown` 删除，不会读写真实 `questions.db`。`BASE_DIR` 必须一并重定向——恢复路径中 `tempfile.mkstemp(dir=BASE_DIR)` 生成的临时文件须与目标同目录，跨卷 `os.replace` 会失败。
- **输入模拟**：用 `unittest.mock.patch('builtins.input', side_effect=[...])` 依次提供模拟输入。
- **覆盖范围**：数据层 10 个用例 + CLI 层 6 个用例 + Web 层 18 个用例（含认证与 CSRF），共 **34 个用例**。

> ⚠️ 测试依赖 `from models import ...` 的值拷贝特性，路径常量必须**双边同步更新**（`models.DATA_FILE = cli.DATA_FILE = ...`），否则会误读写真实数据文件。

---

> 本文档基于源码 v0.2.0（2026-08-16）生成，如代码结构变更请同步更新。
