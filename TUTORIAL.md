# Question Notebook 教学文档

> 用这个项目学 Python：从命令行工具到 Web 应用，从单文件到分层架构。

本教程以 Question Notebook 项目为教材，按"从零到进阶"的顺序讲解。建议配合源码阅读，边看边动手改。

---

## 目录

- [第 0 课：这个项目能教你什么](#第-0-课这个项目能教你什么)
- [第 1 课：数据模型与序列化（models.py）](#第-1-课数据模型与序列化modelspy)
- [第 2 课：命令行交互（question_notebook.py）](#第-2-课命令行交互question_notebookpy)
- [第 3 课：Web 界面与 REST API（web_app.py）](#第-3-课web-界面与-rest-apīweb_apppy)
- [第 4 课：模块化架构思想](#第-4-课模块化架构思想)
- [第 5 课：自动化测试（test_qn.py）](#第-5-课自动化测试test_qnpy)
- [第 6 课：动手练习](#第-6-课动手练习)

---

## 第 0 课：这个项目能教你什么

一个完整的编程项目通常包含这些层次，Question Notebook 全都覆盖了：

| 层次 | 对应代码 | 你将学到 |
|------|---------|---------|
| 数据层 | `models.py` | 类与对象、序列化、文件读写、异常处理 |
| CLI 界面 | `question_notebook.py` | 输入输出、循环菜单、列表推导式 |
| Web 界面 | `web_app.py` / `index.html` | Flask 路由、REST API、前后端交互 |
| 架构 | 整个项目 | 分层设计、单一职责、模块化 |
| 测试 | `test_qn.py` | unittest、mock、测试隔离 |

**学习建议**：不要只读，要动手。每节课后面都有练习，改坏了大不了删掉重来——项目有 Git 版本控制，随时可以回到之前的状态。

## 第 1 课：数据模型与序列化（models.py）

### 1.1 用类表示现实事物

程序要管理"问题"，所以定义一个 `Question` 类，把问题的所有属性打包在一起：

```python
class Question:
    def __init__(self, title, description="", is_solved=False, solution="", category="未分类"):
        self.id = None                      # 唯一编号，保存时自动分配
        self.title = title                  # 标题
        self.description = description      # 描述
        self.timestamp = ...                # 创建时间
        self.is_solved = is_solved          # 是否已解决
        self.solution = solution            # 解决方案
        self.category = category            # 分类
```

**为什么用类而不是字典？** 类把数据和操作数据的方法放在一起，调用方不用记字段名拼写，也不容易写错。比如 `q.title` 比 `q["title"]` 更直观，还能自动补全。

### 1.2 序列化：对象 ↔ 文件

程序运行时的对象存在内存里，关掉程序就没了。要持久化，必须把对象转成能存进文件的格式（JSON），这个过程叫**序列化**；反过来从文件恢复对象叫**反序列化**。

```python
def to_dict(self):          # 对象 → 字典（序列化）
    return {"id": self.id, "title": self.title, ...}

@classmethod
def from_dict(cls, item):   # 字典 → 对象（反序列化）
    q = cls(title=item.get('title', ''), ...)
    q.id = item.get('id')
    return q
```

注意 `from_dict` 里用的是 `item.get('category', '未分类')` 而不是 `item['category']`——`get` 带默认值，**旧数据缺字段时不会报错**，这就是"旧数据兼容"的原理。这是从 7 月 24 日的一次真实 bug 中学来的教训：当时用 `[]` 取值，数据缺字段程序直接崩溃。

### 1.3 文件读写与异常处理

```python
def load_questions():
    if not os.path.exists(DATA_FILE):
        return []                          # 文件不存在：返回空列表
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [Question.from_dict(item) for item in data]
    except json.JSONDecodeError:
        # 文件损坏：备份 .bak 后重建，而不是崩溃
        ...
```

三个要点：

1. **`with open(...)` 自动关闭文件**——忘记关文件是新手最常见的 bug 之一
2. **`encoding='utf-8'` 必须显式指定**——Windows 默认 GBK 编码，读 UTF-8 的中文 JSON 会乱码或报错（这个项目的第一个 bug）
3. **捕获 `JSONDecodeError`**——数据文件被手贱改坏时，程序备份原文件并重建，而不是带着 traceback 崩溃

## 第 2 课：命令行交互（question_notebook.py）

### 2.1 菜单循环模式

命令行程序最经典的结构：**死循环 + 分支分发**。

```python
while True:
    choice = input(">> 请输入选项编号: ")
    if choice == '1':
        list_questions(questions)
    elif choice == '0':
        break
    else:
        print("[警告] 无效输入")
```

这种模式简单、直观，是理解"事件分发"（路由）的起点——Web 框架的路由本质也是这个思想。

### 2.2 列表推导式：一行代替循环

删除功能用了列表推导式：

```python
questions[:] = [q for q in questions if q.id != q_id]
```

等价于：

```python
new_list = []
for q in questions:
    if q.id != q_id:
        new_list.append(q)
questions[:] = new_list
```

**为什么用 `questions[:] = ...` 而不是 `questions = ...`？** 因为前者是"原地修改"——所有持有这个列表的地方都会看到新内容；后者只是让局部变量指向新列表，函数外的数据不变。这是 Python 的经典陷阱，面试常考。

### 2.3 多关键词搜索（AND 逻辑）

搜索功能把问题所有文本拼成一个大字符串，然后要求每个关键词都命中：

```python
keywords = [k.lower() for k in keyword.split()]          # "python 报错" → ["python", "报错"]
searchable_text = " ".join([q.title, q.description, ...]).lower()
if all(k in searchable_text for k in keywords):          # 全部命中才算
    results.append(q)
```

`all()` + 生成器表达式是 Python 处理"全部满足"条件的标准写法，比嵌套循环优雅得多。

### 2.4 二次确认模式

删除这种不可逆操作，先问一次：

```python
confirm = input(f"确认删除吗？(y/N): ").strip().lower()
if confirm != 'y':
    return  # 只有明确输入 y 才继续
```

默认值是大写 `N`，暗示"不确认就不删"。这是安全交互的通用设计。

## 第 3 课：Web 界面与 REST API（web_app.py）

### 3.1 从 CLI 到 Web 的思维转变

CLI 是"程序主动问，用户答"；Web 是"用户主动请求，程序响应"。所以 Web 版把每个操作变成**接口**：

| CLI 操作 | Web 接口 |
|---------|---------|
| 添加问题 | `POST /api/questions` |
| 查看全部 | `GET /api/questions` |
| 编辑问题 | `PUT /api/questions/<id>` |
| 删除问题 | `DELETE /api/questions/<id>` |

这就是 **REST API**：用 HTTP 方法（GET/POST/PUT/DELETE）表达"查/增/改/删"，用 URL 定位资源。

### 3.2 一个完整的接口长什么样

```python
@app.route('/api/questions', methods=['POST'])
def api_add():
    data = request.get_json(force=True)          # 1. 解析请求体（JSON）
    title = (data.get('title') or '').strip()    # 2. 校验数据
    if not title:
        return jsonify({"error": "标题不能为空"}), 400   # 3. 失败：返回错误 + 状态码
    q = Question(title=title, ...)
    questions = load_questions()
    questions.append(q)
    save_questions(questions)
    return jsonify(q.to_dict()), 201             # 4. 成功：返回数据 + 状态码 201
```

接口的固定套路：**解析 → 校验 → 处理 → 返回**。状态码是有语义的：200 成功、201 创建成功、400 参数错误、404 找不到——前端靠状态码判断成功失败，比看返回内容可靠。

### 3.3 前端如何调用

前端页面用 `fetch` 调用接口，异步刷新数据：

```javascript
async function saveEdit() {
    const res = await fetch('/api/questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description, category })
    });
    if (res.ok) {
        load();   // 重新拉取数据并渲染
    }
}
```

**前后端分离**：前端只负责展示和交互，所有数据操作都通过 API 完成。这样以后换前端（比如做手机 App），后端一行都不用改。

## 第 4 课：模块化架构思想

### 4.1 为什么要分层

早期版本只有一个 `question_notebook.py`，Web 版上线时发现 `load_data` 和 CLI 的 `load_questions` 是同一份逻辑写了两遍——**改一个 bug 要改两处，这就是代码腐化的开始**。

解决方案：抽出 `models.py` 数据层，两个界面共用：

```
界面层（CLI / Web）  →  调用  →  数据层（models.py）
```

### 4.2 三条原则

1. **单一职责**：一个模块只做一类事（数据层不管界面，界面层不碰文件）
2. **依赖单向**：界面依赖数据，数据不依赖界面
3. **存储隔离**：以后把 JSON 换成 SQLite/PostgreSQL，界面层完全不用动

### 4.3 真实踩坑：值拷贝陷阱

模块化后测试时发现一个大坑：

```python
# cli.py
from models import DATA_FILE   # 这是"拷贝"了当时的字符串值！
```

测试想重定向数据文件到临时目录，改了 `models.DATA_FILE`，但 `cli.DATA_FILE` 还是旧值——**CLI 依然读写真实文件**。因为 `from ... import ...` 是值拷贝，不是引用。

解决方案有两种：
- 用 `import models` 然后 `models.DATA_FILE`（始终读最新值）
- 测试时两个模块的常量一起改（本项目采用，见 `test_qn.py`）

这是模块化开发中最容易踩的坑之一，理解了它，你对 Python 的模块机制就真正入门了。

## 第 5 课：自动化测试（test_qn.py）

### 5.1 为什么测试很重要

手动测试靠人肉点菜单，改一次代码点一遍，迟早会漏。自动化测试把"验证"变成一条命令：`python test_qn.py`。

### 5.2 模拟用户输入：mock

CLI 靠 `input()` 拿输入，测试时不能真的等键盘，用 `mock` 伪造：

```python
from unittest.mock import patch

with patch('builtins.input', side_effect=["测试问题", "描述", "编程"]):
    cli.add_question(questions)
# side_effect 列表里的值会依次作为 input() 的返回值
```

### 5.3 测试隔离：临时目录

测试会写数据文件，如果直接跑会污染真实数据。解决方案是把数据路径重定向到临时目录：

```python
self.tmpdir = tempfile.mkdtemp(prefix="qn_test_")
models.DATA_FILE = cli.DATA_FILE = os.path.join(self.tmpdir, "questions.json")
```

**注意两边都要改**——就是第 4 课那个值拷贝陷阱的实战应用。

### 5.4 测试要覆盖什么

- **正常流程**：添加 → 编辑 → 解决 → 删除，全链路走一遍
- **边界情况**：数据文件不存在、文件损坏、找不到 ID、非法输入
- **数据兼容**：旧格式数据能否正常加载
- 测试不是证明"程序没 bug"，而是**防止改出新 bug**（回归测试）

## 第 6 课：动手练习

学完理论，动手改代码。以下是按难度排序的练习，做完你就真正吃透了这个项目：

**入门级**
1. 给问题增加"重要程度"字段（高/中/低），列表里用 `★` 显示——体会"加字段要改哪些地方"（提示：models 的 `to_dict`/`from_dict`、CLI 的显示、Web 的表单和卡片）
2. 添加问题时校验标题长度（超过 50 字拒绝）——练习输入校验

**进阶级**
3. 把搜索改成 OR 逻辑（任一关键词命中即可）——对比 AND 实现的差异，思考哪种更实用
4. 给 Web 版加"按分类统计"接口：`GET /api/stats` 返回每个分类的问题数，前端画成柱状图
5. 用 SQLite 替换 JSON 存储——体会"存储隔离"的价值（`models.py` 内部换实现，界面层不动）

**挑战级**
6. 加用户系统：注册/登录，每个用户只能看到自己的问题——这需要给 Question 加 `owner` 字段，是所有社区类应用的第一步
7. 部署到云服务器，让同学通过公网访问——体会从"本地工具"到"线上产品"的完整流程

---

## 学习路线建议

- **零基础**：先读第 1、2 课，配合 CLI 版反复练习，完成入门级练习
- **有基础**：重点看第 3 课（Web）和第 4 课（架构），这是简历面试的高频考点
- **准备面试**：第 4 课的值拷贝陷阱、第 2 课的 `questions[:] =` 原地修改、REST 状态码语义，都是能聊出深度的面试话题

**记住**：读十遍不如改一遍。`git checkout .` 可以撤销所有改动，放心折腾。
