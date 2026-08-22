# Question Notebook 教学文档

> 从一个零基础的问题开始：怎么把「记问题」这件小事，做成一个能命令行操作、能网页打开、还能防并发冲突的完整程序？

本教程以 Question Notebook 项目为教材，按「先跑起来 → 看懂每一层 → 动手改」的顺序，把整个项目的逻辑和代码讲透。**建议边读边对着源码看**，每读一段就打开对应文件核对一遍，这样理解最扎实。

---

## 目录

- [第 0 课：先跑起来，建立整体印象](#第-0-课先跑起来建立整体印象)
- [第 1 课：数据层 models.py —— 数据怎么存](#第-1-课数据层-modelspy--数据怎么存)
- [第 2 课：CLI 层 question_notebook.py —— 命令行怎么交互](#第-2-课-cli-层-question_notebookpy--命令行怎么交互)
- [第 3 课：Web 层 web_app.py —— 从命令行到网页](#第-3-课-web-层-web_apppy--从命令行到网页)
- [第 4 课：架构思想与并发安全](#第-4-课架构思想与并发安全)
- [第 5 课：自动化测试 test_qn.py](#第-5-课自动化测试-test_qnpy)
- [第 6 课：动手练习](#第-6-课动手练习)
- [学习路线建议](#学习路线建议)

---

## 第 0 课：先跑起来，建立整体印象

### 0.1 这个项目是什么

Question Notebook 是一个「问题笔记本」：记录你学习、工作中遇到的问题，标记是否解决、写下解决方案、分类归档，还支持搜索、备份、导出 CSV。

它有两个入口，操作的是**同一份数据**：

| 入口 | 启动命令 | 面向 |
|------|---------|------|
| 命令行（CLI） | `python question_notebook.py` | 键盘交互，菜单式 |
| 网页（Web） | `python web_app.py` | 浏览器点击，界面式 |

### 0.2 先跑一次

```bash
# 1. 确认 Python 版本（需要 3.10+）
python --version

# 2. 跑命令行版
python question_notebook.py

# 3. 跑网页版（需要先装 Flask）
pip install flask
python web_app.py
# 浏览器打开 http://127.0.0.1:5000
```

网页版默认**免登录**（只适合本机用）。要启用登录，加个环境变量：

```bash
# Linux / macOS
QUESTION_NOTEBOOK_PASSWORD=123456 python web_app.py

# Windows PowerShell
$env:QUESTION_NOTEBOOK_PASSWORD="123456"; python web_app.py
```

### 0.3 项目文件结构

```
question_notebook/
├── models.py              # 数据层：数据长什么样、怎么读写 SQLite
├── question_notebook.py   # CLI 界面层：命令行菜单、输入输出
├── web_app.py             # Web 界面层：Flask 路由、认证、CSRF
├── templates/
│   └── index.html         # Web 前端页面（HTML + CSS + JS）
├── test_qn.py             # 自动化测试
├── schema.sql             # SQLite 表结构定义（建表/索引）
├── migrate_to_sqlite.py   # 旧版 JSON → SQLite 一次性迁移脚本
├── questions.db           # SQLite 数据库（首次运行自动生成）
└── ...（README / TUTORIAL / ROADMAP / CODE_WIKI 四份文档）
```

### 0.4 整体架构一句话

程序分成**三层**，依赖方向自上而下，单向流动：

```
界面层（CLI / Web）  ──调用──▶  数据层（models.py）
```

- **数据层**只管「数据是什么、怎么存到数据库」，不知道界面长什么样。
- **界面层**只管「怎么展示、怎么接收输入」，读写数据一律调用数据层。

这样设计的好处：CLI 和 Web 共用同一套数据逻辑，改 bug 只改一处；以后把 SQLite 换成 PostgreSQL，界面层一行都不用改。

---

## 第 1 课：数据层 models.py —— 数据怎么存

数据层是理解整个项目的**地基**。先看它，再看界面层就顺了。

### 1.1 用类表示「问题」

程序要管理一条问题，最直观的做法是定义一个类，把问题的所有属性打包在一起：

```python
class Question:
    def __init__(self, title, description="", is_solved=False,
                 solution="", category="未分类"):
        self.id = None                    # 唯一编号，保存时自动分配
        self.title = title                # 标题
        self.description = description    # 详细描述
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.is_solved = is_solved        # 是否已解决
        self.solution = solution          # 解决方案
        self.category = category          # 分类
```

**为什么用类而不是字典？** 类把「数据」和「操作数据的方法」放在一起，调用方写 `q.title` 而不是 `q["title"]`——前者有代码补全、拼错会直接报错，后者拼错字段名只会得到 `None`，很难排查。

### 1.2 存储介质：为什么用 SQLite

程序运行时，`Question` 对象存在**内存**里，关掉程序就没了。要长期保存，必须把它写到能持久化的介质里。

这个项目用 **SQLite** 数据库存储。SQLite 是一个单文件数据库（`questions.db`），不需要安装单独的数据库服务器，Python 标准库自带 `sqlite3` 模块就能用——对个人工具来说几乎是零成本。

> 小历史：v0.1.x 用的是 JSON 文件存储，v0.2.0 迁到了 SQLite。迁移用的是项目里的 `migrate_to_sqlite.py` 脚本，把旧 `questions.json` 一键导入 `questions.db`。表结构定义在 `schema.sql`。

### 1.3 表结构：数据在数据库里长什么样

在关系型数据库里，数据存在**表**里。表就像一张 Excel 表格：每行是一条记录，每列是一个字段。我们的 `questions` 表有 7 列：

```sql
CREATE TABLE questions (
    id          INTEGER PRIMARY KEY,              -- 主键，唯一标识一条问题
    title       TEXT    NOT NULL,                 -- 标题，必填
    description TEXT    NOT NULL DEFAULT '',      -- 描述
    timestamp   TEXT    NOT NULL,                 -- 创建时间
    is_solved   INTEGER NOT NULL DEFAULT 0        -- 0=未解决, 1=已解决
                CHECK (is_solved IN (0, 1)),
    solution    TEXT    NOT NULL DEFAULT '',      -- 解决方案
    category    TEXT    NOT NULL DEFAULT '未分类'  -- 分类
);
```

几个要点：

1. **`PRIMARY KEY`**：`id` 列是主键，数据库会自动保证它唯一、不为空，并自动建索引加速按 id 查找。
2. **`NOT NULL DEFAULT ...`**：插入时如果没给这一列值，就用默认值，且不允许是 `NULL`。这就是「字段缺失自动补默认值」的原理——由数据库的 schema 约束保证，比代码里逐个判断更可靠。
3. **`CHECK (is_solved IN (0, 1))`**：SQLite 没有真正的布尔类型，用 0/1 表示。`CHECK` 约束防止写入 2、3 这种非法值。
4. **`to_dict` / `from_dict` 仍然保留**：虽然底层是 SQLite，但 Web 接口要返回 JSON、迁移脚本要读旧 JSON，所以 `Question` 类仍提供字典转换方法，作为「对象 ↔ 字典」的桥梁。

### 1.4 读数据库与异常处理

```python
def load_questions():
    if not os.path.exists(DATA_FILE):
        return []                    # 数据库文件不存在：返回空列表
    try:
        conn = _connect()            # 打开数据库连接
    except sqlite3.DatabaseError:
        return _handle_corrupt_db()  # 文件不是有效 SQLite 库 → 备份 .bak 后返回 []
    try:
        _ensure_schema(conn)         # 建表建索引（IF NOT EXISTS，幂等）
        rows = conn.execute(
            "SELECT id, title, description, timestamp, is_solved, solution, category "
            "FROM questions ORDER BY id"
        ).fetchall()
        return [_row_to_question(r) for r in rows]
    except sqlite3.DatabaseError:
        return _handle_corrupt_db()  # 查询失败（库损坏）→ 同样备份后返回 []
    finally:
        conn.close()                 # 用完一定关连接
```

三个要点：

1. **`conn.close()` 放在 `finally`**——数据库连接是稀缺资源，忘记关会泄漏。`finally` 块无论是否出错都会执行。
2. **`_ensure_schema` 幂等建表**——用 `CREATE TABLE IF NOT EXISTS`，第一次运行时建表，之后再调用也不会报错或重建。这样代码不用判断「表存在没有」。
3. **捕获异常而不是崩溃**——如果 `questions.db` 被人手改成乱码（不是有效 SQLite 格式），程序把它备份成 `.bak` 然后从空状态重建，而不是甩一堆 traceback 给用户。`_row_to_question` 还会把 `is_solved` 从 0/1 还原成 Python 的 `bool`。

### 1.5 写数据库：为什么用事务

如果写数据时程序崩溃，可能出现「删了旧数据但新数据没写进去」的中间状态。解决办法是**事务**（transaction）：把「删除全部 + 插入全部」打包成一个不可分割的操作，要么全成功、要么全不变。

```python
def save_questions(questions):
    # 先分配 ID（与存储介质无关的逻辑）
    ...
    conn = _connect()
    try:
        _ensure_schema(conn)
        conn.execute("BEGIN")                 # 开启事务
        conn.execute("DELETE FROM questions") # 清空旧数据
        if questions:
            conn.executemany(                 # 批量插入新数据
                "INSERT INTO questions (...) VALUES (?, ?, ...)",
                [...]
            )
        conn.commit()                         # 提交：整个事务生效
    except Exception:
        conn.rollback()                       # 出错：回滚，什么都没发生
        raise
    finally:
        conn.close()
```

关键在 `BEGIN` / `commit` / `rollback` 三件套：

- `BEGIN`：开始一个事务，之后的 SQL 都在一个「未决」状态。
- `commit()`：把事务里的改动**真正写入**数据库。
- `rollback()`：撤销事务里的所有改动，回到 `BEGIN` 之前的状态。

如果 `DELETE` 成功了但 `INSERT` 报错，`rollback` 会让 `DELETE` 也失效——数据不会丢。这就是事务的「要么全做、要么全不做」（原子性）。

> **参数化查询防 SQL 注入**：注意 `INSERT ... VALUES (?, ?, ...)` 里的 `?` 占位符，值通过 `executemany` 的第二个参数传入。**永远不要**用字符串拼接（`f"INSERT ... VALUES ({title})"`）构造 SQL——用户输入里如果有单引号就能注入恶意 SQL，`?` 占位符会自动转义。

### 1.6 备份、恢复、导出

这几个功能 CLI 和 Web 都要用，所以统一下沉到数据层：

| 函数 | 作用 |
|------|------|
| `backup_data()` | 把当前 `questions.db` 复制到 `backups/` 目录，文件名带微秒时间戳 |
| `list_backups()` | 列出所有备份文件（新的在前） |
| `restore_data(filename)` | 用**正则白名单**校验文件名后，把备份 `.db` 原子替换回数据文件 |
| `build_csv(questions)` | 生成 CSV 字符串（带 UTF-8 BOM 头，Excel 打开不乱码） |

`restore_data` 有两个安全细节：

1. **白名单校验**：只接受 `questions_YYYYMMDD_HHMMSS_微秒.db` 这种命名，拒绝 `../xxx` 这类路径——防止别人用 `../` 穿越目录去覆盖任意文件。
2. **原子替换**：恢复时先复制备份到同目录临时文件，再用 `os.replace` 原子替换目标库，避免恢复中途崩溃导致数据库损坏。

### 1.7 跨进程锁：多人同时写怎么办

如果 CLI 和 Web 同时运行，两个进程都执行「读 → 改 → 写」，可能互相覆盖（后写的把先写的盖掉）。单进程内的锁（`threading.Lock`）管不住**跨进程**，所以用文件锁：

```python
@contextlib.contextmanager
def data_lock():
    with open(lock_path, 'r+') as f:
        if os.name == 'nt':           # Windows
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        else:                         # Linux / macOS
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield                     # 锁内执行「读-改-写」
        finally:
            # 释放锁
            ...
```

用法：

```python
with data_lock():
    questions = load_questions()   # 读
    questions.append(new_q)        # 改
    save_questions(questions)      # 写
```

**为什么要锁**：三个步骤必须「原子地」执行，中间不能插进另一个进程的写操作。文件锁让操作系统保证同一时刻只有一个进程能拿到锁，其他进程排队等待。

> 注意锁**不能重入**（同一进程拿两次会死锁），所以锁放在调用方的事务层，`save_questions` 内部不再加锁。SQLite 自己也有锁，这个应用层文件锁先行串行化，能避免直接撞上 SQLite 的 "database is locked" 错误。

---

## 第 2 课：CLI 层 question_notebook.py —— 命令行怎么交互

CLI 层不碰文件细节，只负责「打印菜单、读输入、调数据层」。理解它，就理解了「界面层」该长什么样。

### 2.1 菜单循环：程序的主骨架

`main()` 是入口，结构是经典的「死循环 + 分支分发」：

```python
def main():
    questions = load_questions()     # 启动时加载一次数据
    while True:
        # 打印菜单
        choice = input(">> 请输入选项编号: ")
        if choice == '1':
            list_questions(questions)
        elif choice == '2':
            add_question(questions)
        # ... 其余分支
        elif choice == '0':
            break                    # 退出循环，程序结束
        else:
            print("[警告] 无效输入")
```

这种「根据输入分发到不同函数」的模式，本质就是**事件分发**——Web 框架的路由（`@app.route`）也是同一个思想，只是输入从键盘换成了 HTTP 请求。

### 2.2 添加问题：input 拿输入，锁内写数据

```python
def add_question(questions):
    title = input("请输入问题标题: ")
    if not title.strip():            # 标题为空/全空格：取消
        print("标题不能为空，取消添加。")
        return
    description = input("请输入问题详细描述 (可选): ")
    category = input("请输入分类 (可选): ").strip() or "未分类"

    with data_lock():                # 锁内：读 → 改 → 写
        latest = load_questions()    # 重新读磁盘最新数据
        new_q = Question(title=title, description=description, category=category)
        latest.append(new_q)
        save_questions(latest)
        questions.clear()
        questions.extend(latest)     # 同步内存快照
```

两个值得注意的设计：

1. **`input()` 放在锁外**——用户输入可能很慢（想半天），如果持锁等输入，其他进程就被卡住了。所以锁内只做「读-改-写」这一瞬间的数据操作。
2. **锁内重新 `load_questions()`**——不直接用内存里的 `questions`，而是读磁盘最新数据，避免覆盖 Web 端刚写入的内容。

### 2.3 `_refresh`：让 CLI 看到 Web 的最新改动

CLI 启动时加载了一次 `questions`，之后如果 Web 端改了数据，CLI 内存里的就是旧的了。所以每个**读操作**前都先刷新：

```python
def _refresh(questions):
    questions.clear()
    questions.extend(load_questions())   # 从磁盘重新加载
```

`list_questions`、`search_questions`、`filter_questions`、`view_by_category`、`export_csv` 开头都会调它。这就是「CLI 和 Web 数据实时互通」的秘密。

### 2.4 列表推导式：一行代替循环

删除功能用列表推导式原地过滤：

```python
latest[:] = [q for q in latest if q.id != q_id]
```

等价于：

```python
new_list = []
for q in latest:
    if q.id != q_id:
        new_list.append(q)
latest[:] = new_list
```

**为什么写 `latest[:] = ...` 而不是 `latest = ...`？** 前者是「原地修改」——所有持有这个列表引用的地方都看到新内容；后者只是让局部变量指向一个新列表，外面的 `questions` 还是旧的。这是 Python 经典陷阱。

### 2.5 `next()` 找元素

按 ID 找问题时用了生成器表达式 + `next()`：

```python
target_q = next((q for q in latest if q.id == q_id), None)
```

含义：找到第一个 `id == q_id` 的返回它；找不到返回 `None`。比写 `for` 循环 + 标志位简洁得多。

### 2.6 二次确认：防误删

删除、恢复这类不可逆操作，都先问一次：

```python
confirm = input(f"确认删除问题 '{target_q.title}' 吗？(y/N): ").strip().lower()
if confirm != 'y':
    print("[提示] 已取消删除。")
    return
```

默认值是大写 `N`，暗示「不确认就不删」——只有明确输入 `y` 才继续。这是安全交互的通用设计。

---

## 第 3 课：Web 层 web_app.py —— 从命令行到网页

### 3.1 从 CLI 到 Web 的思维转变

CLI 是「程序主动问，用户答」；Web 是「用户主动请求，程序响应」。所以 Web 版把每个操作变成一个**接口（API）**：

| CLI 操作 | Web 接口 |
|---------|---------|
| 查看全部 | `GET /api/questions` |
| 添加问题 | `POST /api/questions` |
| 编辑问题 | `PUT /api/questions/<id>` |
| 删除问题 | `DELETE /api/questions/<id>` |

这就是 **REST API**：用 HTTP 方法（GET/POST/PUT/DELETE）表达「查/增/改/删」，用 URL 定位资源。

### 3.2 一个完整接口的套路

看添加问题的接口：

```python
@app.route('/api/questions', methods=['POST'])
def api_add():
    data = _get_json_body()                    # 1. 解析请求体
    if data is None:
        return jsonify({"error": "请求体必须是 JSON"}), 400   # 2. 校验
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({"error": "标题不能为空"}), 400
    with data_lock():                          # 3. 处理（加锁）
        q = Question(title=title, ...)
        questions = load_questions()
        questions.append(q)
        save_questions(questions)
    return jsonify(q.to_dict()), 201           # 4. 返回 + 状态码
```

固定套路是**解析 → 校验 → 处理 → 返回**。状态码有语义：`200` 成功、`201` 创建成功、`400` 参数错误、`401` 未登录、`403` 无权限、`404` 找不到。前端靠状态码判断成败，比解析返回文本可靠。

### 3.3 `_get_json_body`：只收对象

```python
def _get_json_body():
    data = request.get_json(force=True, silent=True)  # 解析失败返回 None
    if not isinstance(data, dict):                    # 只接受对象
        return None
    return data
```

如果请求体是数组 `[1,2,3]` 或字符串，后续 `.get()` 会崩溃，所以这里**只接受字典**，其他一律当非法返回 `400`。

### 3.4 认证：密码登录

网页要能安全地暴露给别人用，就不能谁都能增删改。认证逻辑：

```python
# 启动时：读环境变量，有密码就启用认证
_AUTH_PASSWORD = os.environ.get("QUESTION_NOTEBOOK_PASSWORD", "").strip()
AUTH_ENABLED = bool(_AUTH_PASSWORD)

# 密码不存明文，用 PBKDF2 哈希 + 盐
_AUTH_HASH = hashlib.pbkdf2_hmac("sha256", _AUTH_PASSWORD.encode(), _AUTH_SALT, 100_000)

def _password_verify(password):
    d = hashlib.pbkdf2_hmac("sha256", password.encode(), _AUTH_SALT, 100_000)
    return hmac.compare_digest(d, _AUTH_HASH)   # 常量时间比较，防时序攻击
```

三个安全要点：

1. **不存明文密码**——存的是 PBKDF2 哈希（加了随机盐、迭代 10 万次），即使文件泄露也推不出原密码。
2. **`hmac.compare_digest` 比较**——普通 `==` 比较会「逐字符、早返回」，攻击者能靠响应时间猜密码长度；`compare_digest` 恒定时间，堵住这个口子。
3. **登录写进 session**——`session["logged_in"] = True`，之后用 `@_require_auth` 装饰器保护接口。

```python
def _require_auth(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if AUTH_ENABLED and not session.get("logged_in"):
            return jsonify({"error": "未登录"}), 401
        return view_func(*args, **kwargs)
    return wrapper
```

所有问题接口（`api_list` / `api_add` / ...）都套上了 `@_require_auth`。没设密码时 `AUTH_ENABLED` 为 `False`，装饰器直接放行，等于免登录。

### 3.5 CSRF：防止「假请求」

CSRF（跨站请求伪造）攻击：恶意网站诱导已登录用户的浏览器，偷偷向你的站点发一个写请求。因为浏览器会带上你的登录 cookie，服务端分不清是不是你本人点的。

防御方式：每个会话发一个随机 token，写请求必须带上它：

```python
def _ensure_csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)   # 随机生成
        session["_csrf_token"] = token
    return token

@app.before_request
def _csrf_protection():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return                              # 读请求不校验
    expected = session.get("_csrf_token")
    received = request.headers.get("X-CSRF-Token")
    if not expected or not received or not hmac.compare_digest(expected, received):
        if request.path == "/api/login" and request.method == "POST":
            return                          # 登录接口豁免（登录前还没有 token）
        return jsonify({"error": "CSRF 校验失败"}), 403
```

`@app.before_request` 会在**每个请求前**执行。恶意网站不知道你的 token（它藏在你的 session 里、通过 `/api/csrf` 或页面下发），所以伪造的请求会被 `403` 拒绝。

### 3.6 前端 index.html 如何配合

前端用统一的 `api()` 函数发请求，自动带 token、自动处理登录：

```javascript
async function api(url, opts = {}) {
    const headers = Object.assign({}, opts.headers || {});
    headers['X-CSRF-Token'] = __csrf_token;   // 每个请求都带 token
    const res = await fetch(url, {...opts, headers});
    if (res.status === 401) {                 // 未登录：跳登录页
        showLoginPage();
        throw new Error('未登录');
    }
    if (!res.ok) throw new Error(...);
    return res.json();
}
```

登录成功后，后端返回新的 token，前端存进 `__csrf_token`，后续请求继续带。这样前后端配合，把「认证 + CSRF」这套安全机制完整跑通。

### 3.7 数据可视化：SQL 聚合 + Canvas 绘图

v0.2.1 加了「数据可视化」面板——点开后画出分类分布柱状图和解决率环形图。它体现了一个很重要的分工：**统计在数据库算，画图在浏览器画**。

**后端：用 SQL 一次算完，不在 Python 里遍历**

如果用 Python 遍历所有问题再数数，数据量大时会慢。关系型数据库天生擅长聚合，用一条 `GROUP BY` 就行：

```python
def get_stats():
    # 分类分布：每类的总数 + 已解决数，一次 GROUP BY 搞定
    rows = conn.execute(
        "SELECT category, COUNT(*) AS total, SUM(is_solved) AS solved "
        "FROM questions GROUP BY category ORDER BY total DESC, category"
    ).fetchall()
```

两个细节：

1. **`SUM(is_solved)`**：`is_solved` 存的是 0/1，`SUM` 直接得到已解决数——这是「用整数表示布尔」的妙用。
2. **`substr(timestamp, 1, 7)`**：从 `"2026-08-22 14:30:00"` 截出 `"2026-08"`，再 `GROUP BY` 就得到按月统计。

后端 `/api/stats` 只是把 `get_stats()` 的结果 `jsonify` 转发，不做任何加工——这叫「薄接口」。

**前端：原生 Canvas 画图，零依赖**

图表用浏览器自带的 `<canvas>` + `getContext('2d')` 画，不引入任何第三方库（ECharts/Chart.js 都不用）。好处是没有依赖、加载快、可控；代价是要自己算坐标。柱状图的核心是算每根柱的位置和高度：

```javascript
const totalH = (c.total / maxVal) * plotH;   // 柱高 = 占比 × 绘图区高度
const solvedH = (c.solved / maxVal) * plotH; // 已解决段高度
ctx.fillStyle = '#15803d';                   // 绿色=已解决（顶部）
ctx.fillRect(x, bottom - totalH, barW, solvedH);
ctx.fillStyle = '#b45309';                   // 橙色=未解决（底部）
ctx.fillRect(x, bottom - totalH + solvedH, barW, totalH - solvedH);
```

环形图则是画两个圆弧：先画一整圈橙色（未解决），再从 12 点方向扫 `solvedFrac` 比例的绿色弧，最后用 `destination-out` 合成模式挖空内圈变成「环」。

**随数据实时刷新**：`load()` 在增删改之后都会调一次 `loadStats()`，面板展开就重画、折叠就只更新右上角数字——这是「数据驱动视图」的朴素实现。

> 这个分工模式（后端聚合 + 前端渲染）是真实数据看板的标配。理解了它，以后换 ECharts 只是换「画图那一步」，统计逻辑一行都不用改。

---

## 第 4 课：架构思想与并发安全

### 4.1 为什么要分层

早期版本只有一个 `question_notebook.py`，Web 版上线时发现：`load_data` 和 CLI 的 `load_questions` 是**同一份逻辑写了两遍**——改一个 bug 要改两处，这就是「代码腐化」的开始。

解法是抽出 `models.py` 数据层，两个界面共用：

```
界面层（CLI / Web）  →  调用  →  数据层（models.py）
```

### 4.2 三条设计原则

1. **单一职责**：一个模块只做一类事（数据层不管界面，界面层不碰数据库）。
2. **依赖单向**：界面依赖数据，数据不依赖界面。
3. **存储隔离**：数据库读写集中在 `models.py`，以后换 PostgreSQL 界面层零改动。

### 4.3 真实踩坑：值拷贝陷阱

```python
# cli.py
from models import DATA_FILE   # 这是「拷贝」了当时的字符串值！
```

测试想重定向数据文件到临时目录，改了 `models.DATA_FILE`，但 `cli.DATA_FILE` 还是旧值——CLI 依然读写真实文件。因为 `from ... import ...` 是**值拷贝**，不是引用。

两种解法：
- 用 `import models` 然后 `models.DATA_FILE`（始终读最新值）。
- 测试时两个模块的常量一起改（本项目采用，见 `test_qn.py`）。

> **进阶坑**：测试隔离还要求 `BASE_DIR` 也要一起重定向——因为 `restore_data` 做原子替换时临时文件要和目标文件同目录（`os.replace` 跨文件系统会失败）。

### 4.4 并发安全：三个层次的演进

这个项目在并发安全上走过三个阶段，很值得体会：

| 阶段 | 做法 | 能防什么 |
|------|------|---------|
| 1. 无锁 | 直接读改写 | 单进程顺序执行没问题 |
| 2. `threading.Lock` | 进程内线程锁 | Flask 多线程并发写 |
| 3. `data_lock`（文件锁） | 跨进程文件锁 | CLI 和 Web 两个进程同时写 |

第 2 阶段只能管住**同一个进程里的多线程**；一旦 CLI 和 Web 是两个独立进程，`threading.Lock` 就失效了，所以升级成操作系统级的文件锁。理解「锁的作用范围」是并发编程的核心。

---

## 第 5 课：自动化测试 test_qn.py

### 5.1 为什么测试很重要

手动测试靠人肉点菜单，改一次代码点一遍，迟早漏。自动化测试把「验证」变成一条命令：

```bash
python test_qn.py
# 或
python -m unittest test_qn
```

跑一遍，34 个用例全绿，就说明这次改动没把已有功能改坏。

### 5.2 模拟用户输入：mock

CLI 靠 `input()` 拿输入，测试时不能真的等键盘，用 `mock` 伪造：

```python
from unittest.mock import patch

with patch('builtins.input', side_effect=["测试问题", "描述", "编程"]):
    cli.add_question(questions)
# side_effect 列表里的值，会依次作为 input() 的返回值
```

### 5.3 测试隔离：临时目录

测试要写数据库，直接跑会污染真实 `questions.db`。解法是把路径重定向到临时目录：

```python
self.tmpdir = tempfile.mkdtemp(prefix="qn_test_")
models.BASE_DIR = cli.BASE_DIR = self.tmpdir
models.DATA_FILE = cli.DATA_FILE = os.path.join(self.tmpdir, "questions.db")
```

**注意两边都要改**——这正是第 4 课「值拷贝陷阱」的实战应用。`BASE_DIR` 也要一起改，因为 `restore_data` 做原子替换时临时文件与目标文件须同目录。

### 5.4 Web 测试：test_client + CSRF

Web 层不启动真实服务器，用 Flask 自带的 `test_client` 模拟请求：

```python
self.c = self.app.test_client()
r = self.c.get('/api/csrf')              # 先拿 CSRF token
self._csrf = r.get_json()["token"]
# 之后每个写请求都带这个 token
self.c.post('/api/questions', json={...}, headers={"X-CSRF-Token": self._csrf})
```

因为项目开了 CSRF，测试写请求必须带 token，否则会被 `403` 挡住。测试里还专门验证了「不带 token 会被拒绝」这件事本身——**安全机制也要有测试兜底**。

### 5.5 测试覆盖什么

- **正常流程**：增 → 改 → 解决 → 删，全链路走一遍。
- **边界情况**：数据库不存在、数据库损坏（非 SQLite 格式）、找不到 ID、非法输入、空标题。
- **数据约束**：schema DEFAULT 约束补默认值、SQLite 文件格式校验。
- **安全**：缺/错 CSRF token 拒绝、未登录 401、登录成功/失败、登出失效。

测试不是证明「程序没 bug」，而是**防止改出新 bug**（回归测试）。

---

## 第 6 课：动手练习

学完理论，动手改代码。以下按难度排序，做完你就真正吃透了这个项目。

**入门级**

1. 给问题增加「重要程度」字段（高/中/低），列表里用 `★` 显示——体会「加一个字段要改哪些地方」（提示：`schema.sql` 与 `models.py` 内联的 `_SCHEMA_SQL` 加列、`Question` 的 `to_dict`/`from_dict`、CLI 的显示、Web 的表单和卡片；注意旧 `questions.db` 已有数据，需考虑兼容——`ALTER TABLE ADD COLUMN ... DEFAULT ...` 是不破坏旧数据的加列方式）。
2. 添加问题时校验标题长度（超过 50 字拒绝）——练习输入校验。

**进阶级**

3. 把搜索改成 OR 逻辑（任一关键词命中即可）——对比 AND 实现的差异，思考哪种更实用。
4. 给「数据可视化」面板加第三张图：**按月趋势折线图**——`/api/stats` 已经返回了 `by_month` 数据（每月总数 + 已解决数），用 Canvas 画两条折线（总数线 + 已解决线），体会「数据已就绪，只是换一种画法」。
5. 把 `save_questions` 的「DELETE 全表 + INSERT 全部」改成「只更新变化的那几行」——体会「全量覆盖」与「增量更新」的取舍（提示：用 `UPDATE`/`DELETE WHERE id=?`/`INSERT`，需要跟踪哪些是新增/修改/删除）。

**挑战级**

6. 把登录密码改成「每个用户一套」（多用户系统）——给 `Question` 加 `owner` 字段，这是所有社区类应用的第一步。
7. 部署到云服务器，让同学通过公网访问——体会从「本地工具」到「线上产品」的完整流程（记得先设 `QUESTION_NOTEBOOK_PASSWORD`）。

---

## 学习路线建议

- **零基础**：先读第 0、1、2 课，配合 CLI 版反复练习，完成入门级练习。
- **有基础**：重点看第 3 课（Web + 认证 + CSRF）和第 4 课（架构 + 并发），这是简历面试的高频考点。
- **准备面试**：以下话题都能聊出深度——
  - 值拷贝陷阱（`from ... import` 是值拷贝）
  - `questions[:] = ...` 原地修改 vs 重新赋值
  - REST 状态码语义
  - 数据库事务（`BEGIN`/`commit`/`rollback`）与跨进程文件锁
  - 参数化查询防 SQL 注入（`?` 占位符 vs 字符串拼接）
  - SQL 聚合（`GROUP BY` / `SUM` / `substr`）与「整数表示布尔」的妙用
  - 密码哈希（PBKDF2 + 盐）与防时序攻击（`hmac.compare_digest`）
  - CSRF 攻击原理与 token 防御
  - 前后端分工：后端聚合 + 前端 Canvas 渲染（数据看板标配）

**记住**：读十遍不如改一遍。项目有 Git 版本控制，`git checkout .` 可以撤销所有改动，放心折腾。
