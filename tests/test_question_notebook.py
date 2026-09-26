# -*- coding: utf-8 -*-
"""
test_question_notebook.py - Question Notebook 自动化测试

运行方式（都支持，结果一致）：
    在项目根目录执行：
        python tests/test_question_notebook.py   # 无需安装任何东西（只用 Python 标准库）
        pytest                                   # 装了 pytest 后：输出更清晰，可筛选、重跑

    也可以在 tests/ 目录里执行：
        python test_question_notebook.py

覆盖范围：
- 数据层（models）：模型序列化往返、读写循环、旧数据兼容、损坏文件容错
- CLI 层（cli）：完整业务流程、备份恢复、CSV 导出、分类浏览、多关键词搜索
- Web 层（web）：增删改查、CSRF 防护、登录登出、统计接口

安全说明：测试会把数据路径重定向到项目内的 .tmp/ 临时目录，不会读写真实的
questions.db。临时目录放在项目内（而非系统临时目录）有两个原因：
  1. 沙箱/受限环境下，系统临时目录往往不可写，测试会直接报 PermissionError；
  2. 所有测试产物集中在项目内，随时可以整体删除，不污染系统磁盘。
"""
import contextlib
import hashlib
import inspect
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

# ---------- 让测试在「未安装」状态下也能导入本项目 ----------
# 本文件在 tests/ 下，而代码在 src/question_notebook/ 下，是分开的目录。
# Python 默认不会去 src/ 里找模块，所以这里手动把 src/ 插进搜索路径。
#
# 正规做法是 `pip install -e .`（见 STANDARDS.md），但那是**额外前提**；
# 这段引导保证"刚克隆下来、什么都没装"也能直接跑测试。
# 必须放在导入 question_notebook 之前执行。
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from question_notebook import cli, models  # noqa: E402  (路径引导必须先执行)

# 检测 Flask 是否可用：未安装时跳过 Web 接口测试，数据层/CLI 测试照常运行
try:
    import flask  # noqa: F401
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False


def _make_test_tmpdir():
    """在项目内的 .tmp/ 下创建唯一临时目录，返回其绝对路径。

    为什么不用 tempfile.mkdtemp()：
      1. 它默认把目录建在系统临时目录（Windows 为 %TEMP%），在受限沙箱环境下
         系统临时目录不可写，测试会因为 PermissionError 直接失败；
      2. 部分沙箱实现会拦截对 mkdtemp 所建目录的后续写入。
    因此这里改为「os.makedirs + 随机后缀」自建目录：既落在项目内（随时可整体
    删除、不污染系统盘），又不受上述限制。目录名唯一，用例之间互不干扰。

    万一 .tmp/ 本身不可写（如只读介质），再退回系统临时目录，保证测试总能跑。
    """
    base = os.path.join(PROJECT_ROOT, ".tmp")
    try:
        os.makedirs(base, exist_ok=True)
        tmpdir = os.path.join(base, "qn_test_" + uuid.uuid4().hex[:8])
        os.makedirs(tmpdir, exist_ok=False)  # 随机后缀保证不会重名
        return tmpdir
    except OSError:
        return tempfile.mkdtemp(prefix="qn_test_")


def _remove_tmpdir(path):
    """删除测试临时目录；失败时打印警告，绝不静默吞掉。

    为什么不用 shutil.rmtree(..., ignore_errors=True)：
      它在 Windows 上常因「文件只读 / 目录正被占用 / 沙箱拦截」而删除失败，
      却一个字都不报。结果是 .tmp/ 里悄悄堆积成百上千个垃圾目录，无人察觉。
      这里改为：先正常删；遇到失败就把目标改成可写再重试一次；仍失败则明确警告。

    返回值：True 表示已删除，False 表示删除失败（已警告）。
    """
    if not os.path.exists(path):
        return True

    def _force_writable(func, target, _exc_info):
        """shutil 的失败回调：去掉只读属性后重试该操作。"""
        try:
            os.chmod(target, 0o700)
            func(target)
        except OSError:
            pass  # 交给外层统一判断是否真的删掉了

    try:
        shutil.rmtree(path, onerror=_force_writable)
    except OSError:
        pass

    if os.path.exists(path):
        print(f"[警告] 测试临时目录删除失败：{path}（可手动删除）", file=sys.stderr)
        return False

    # 顺手清理：若 .tmp/ 已空则一并移除，不给项目留下空目录。
    # os.rmdir 只在目录为空时成功，因此不会误删其他用例正在使用的目录。
    try:
        os.rmdir(os.path.join(PROJECT_ROOT, ".tmp"))
    except OSError:
        pass  # 目录非空（其他用例还在用）或不存在，属于正常情况
    return True


class QuestionNotebookTestCase(unittest.TestCase):
    """所有测试类的公共基类：负责数据隔离与输出降噪。

    每个用例开始前：
      1. 新建独立的临时目录，把 models 的数据路径全部指向它
         → 用例之间互不干扰，也绝不碰真实的 questions.db
      2. 把标准输出暂时"关掉" → CLI 的菜单、提示语不再刷屏，
         测试结果一目了然（打印语句的执行本身不受影响）

    用例结束后：删除临时目录、恢复标准输出。即使用例失败也一定会执行（tearDown）。
    """

    def setUp(self):
        self.tmpdir = _make_test_tmpdir()
        # 数据层通过 models 模块属性动态定位文件，因此只需改这里一处
        models.BASE_DIR = self.tmpdir
        models.DATA_FILE = os.path.join(self.tmpdir, "questions.db")
        models.BACKUP_DIR = os.path.join(self.tmpdir, "backups")
        models.EXPORT_DIR = os.path.join(self.tmpdir, "exports")

        # 静音标准输出：测试期间所有 print() 都写进内存缓冲区，不显示在终端
        self._stdout_ctx = contextlib.redirect_stdout(io.StringIO())
        self._stdout_ctx.__enter__()

    def tearDown(self):
        self._stdout_ctx.__exit__(None, None, None)
        _remove_tmpdir(self.tmpdir)


class TestModels(QuestionNotebookTestCase):
    """数据层测试"""

    def test_models_path_constants_contract(self):
        """models.py 必须把四个路径常量都导入进来（源码级契约检查）。

        为什么这条测试要读源码、而不在运行时检查 `hasattr(models, name)`：
            cli.py 用 `models.EXPORT_DIR` 这种**模块属性**读取路径，所以
            "models 上挂着哪些路径名"是对外契约。但本测试基类在 setUp 里会给
            models 赋这四个属性（用于数据隔离），于是**任何运行时检查都会被
            测试自己制造的属性骗过**——哪怕 models.py 里根本没导入它们。
            实测：把 EXPORT_DIR 从 models.py 的导入里删掉，运行时断言照样通过，
            而 `python run_cli.py` 一执行「导出 CSV」就抛 AttributeError。
        因此这里改为直接检查源码中的导入语句——这正是"只有源码才是真相"的一个
        具体例子（同类问题还有 test_export_respects_export_dir_override 兜底）。
        """
        src = inspect.getsource(models)
        self.assertRegex(
            src,
            r"from \.paths import[^\n]*\bEXPORT_DIR\b",
            "models.py 必须从 .paths 导入 EXPORT_DIR（cli.py 通过 models.EXPORT_DIR 使用它）",
        )
        for name in ("DATA_FILE", "BACKUP_DIR", "BASE_DIR"):
            self.assertRegex(
                src,
                rf"from \.paths import[^\n]*\b{name}\b",
                f"models.py 必须从 .paths 导入 {name}",
            )

    def test_export_respects_export_dir_override(self):
        """导出功能必须使用 models.EXPORT_DIR 当前的值（而非某个写死的目录）。

        TestCLI.test_export_csv 验证的是"导出内容带 BOM"；本用例验证"导出位置
        可被重定向"——测试隔离正是靠这个能力（见 STANDARDS 第 4 节）。
        """
        custom = os.path.join(self.tmpdir, "exports_custom")
        models.EXPORT_DIR = custom
        questions = [models.Question(title="导出路径测试", category="测试")]
        models.save_questions(questions)

        cli.export_csv(questions)

        self.assertTrue(os.path.isdir(custom), "导出目录未被创建，说明没有使用 models.EXPORT_DIR")
        self.assertEqual(len(os.listdir(custom)), 1)

    def test_question_roundtrip(self):
        """模型序列化与反序列化往返一致"""
        q = models.Question(title="测试", description="描述", category="编程")
        q.id = 1
        q.timestamp = "2026-08-15 18:00:00"
        q2 = models.Question.from_dict(q.to_dict())
        self.assertEqual(q2.id, 1)
        self.assertEqual(q2.title, "测试")
        self.assertEqual(q2.category, "编程")
        self.assertEqual(q2.timestamp, "2026-08-15 18:00:00")

    def test_save_load_roundtrip(self):
        """保存后重新加载，数据一致且 ID 自动分配"""
        questions = [models.Question(title="A", category="编程"),
                     models.Question(title="B")]
        models.save_questions(questions)
        self.assertEqual(questions[0].id, 1)
        self.assertEqual(questions[1].id, 2)

        loaded = models.load_questions()
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].title, "A")
        self.assertEqual(loaded[1].category, models.DEFAULT_CATEGORY)

    def test_schema_defaults(self):
        """直接 INSERT 时缺 category：由 schema DEFAULT 补'未分类'"""
        import sqlite3
        models.save_questions([models.Question(title="种子")])  # 建库建表
        conn = sqlite3.connect(models.DATA_FILE)
        conn.execute(
            "INSERT INTO questions (id, title, timestamp) VALUES (?, ?, ?)",
            (99, "无分类行", "2026-08-15 18:00:00"),
        )
        conn.commit()
        conn.close()
        loaded = models.load_questions()
        row = next(q for q in loaded if q.id == 99)
        self.assertEqual(row.category, models.DEFAULT_CATEGORY)
        self.assertEqual(row.description, "")   # DEFAULT ''
        self.assertEqual(row.solution, "")      # DEFAULT ''
        self.assertFalse(row.is_solved)         # DEFAULT 0

    def test_corrupt_db(self):
        """损坏的数据库文件（非 SQLite 格式）：备份 .bak 后返回空列表，不崩溃"""
        with open(models.DATA_FILE, 'w', encoding='utf-8') as f:
            f.write("{损坏的JSON")
        loaded = models.load_questions()
        self.assertEqual(loaded, [])
        self.assertTrue(os.path.exists(models.DATA_FILE + ".bak"))

    def test_non_db_file_treated_as_corrupt(self):
        """文件存在但不是有效 SQLite 库（JSON 对象/字符串/数字）：按损坏处理，不崩溃"""
        for bad in ('{"a": 1}', '"just a string"', "123"):
            # 每个用例前清掉上次的 .bak
            if os.path.exists(models.DATA_FILE + ".bak"):
                os.remove(models.DATA_FILE + ".bak")
            with open(models.DATA_FILE, 'w', encoding='utf-8') as f:
                f.write(bad)
            loaded = models.load_questions()
            self.assertEqual(loaded, [], f"内容为 {bad[:20]} 时应返回空列表")
            self.assertTrue(os.path.exists(models.DATA_FILE + ".bak"))

    def test_atomic_save(self):
        """原子写入：保存后无 .tmp 残留，数据完整"""
        questions = [models.Question(title="原子测试")]
        models.save_questions(questions)
        # 不应残留临时文件
        leftovers = [f for f in os.listdir(models.BASE_DIR) if f.endswith(".tmp")]
        self.assertEqual(leftovers, [])
        loaded = models.load_questions()
        self.assertEqual(len(loaded), 1)

    def test_db_file_is_valid_sqlite(self):
        """保存后数据文件是有效的 SQLite 库（文件头魔数 + 可查表）"""
        import sqlite3
        questions = [models.Question(title="格式测试")]
        models.save_questions(questions)
        # SQLite 文件头魔数：前 16 字节 "SQLite format 3\000"
        with open(models.DATA_FILE, 'rb') as f:
            header = f.read(16)
        self.assertTrue(header.startswith(b"SQLite format 3"))
        # 能正常打开并查询到表与数据
        conn = sqlite3.connect(models.DATA_FILE)
        rows = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        conn.close()
        self.assertEqual(rows, 1)

    def test_backup_name_unique_and_filtered(self):
        """备份文件名含微秒；list_backups 只认符合规范的文件"""
        questions = [models.Question(title="备份测试")]
        models.save_questions(questions)
        name1 = models.backup_data()
        name2 = models.backup_data()  # 同秒连续备份也不覆盖
        self.assertNotEqual(name1, name2)
        # 放一个不合规文件，不应被列出
        with open(os.path.join(models.BACKUP_DIR, "evil.json"), 'w', encoding='utf-8') as f:
            f.write("{}")
        backups = models.list_backups()
        self.assertEqual(len(backups), 2)
        self.assertTrue(all(models.BACKUP_NAME_PATTERN.match(n) for n in backups))

    def test_restore_rejects_bad_names(self):
        """restore_data 拒绝非法文件名（路径穿越/前缀不符）"""
        questions = [models.Question(title="恢复测试")]
        models.save_questions(questions)
        models.backup_data()
        for bad in ("../questions.json", "evil.json", "questions.json",
                    "questions_20260101_000000.json/../../x", ""):
            self.assertFalse(models.restore_data(bad), f"应拒绝: {bad}")
        # 合法文件名应成功
        good = models.list_backups()[0]
        self.assertTrue(models.restore_data(good))

    def test_build_csv(self):
        """CSV 生成：含 BOM 头、表头、数据行"""
        questions = [models.Question(title="CSV测试", category="测试", description="描述")]
        models.save_questions(questions)
        content = models.build_csv(questions)
        self.assertTrue(content.startswith('\ufeff'))
        lines = content.strip().split('\n')
        self.assertEqual(lines[0].rstrip('\r'), '\ufeff' + "ID,标题,描述,创建时间,是否已解决,解决方案,分类")
        self.assertIn("CSV测试", lines[1])

    def test_get_stats(self):
        """get_stats：SQL 聚合正确（分类分布 + 解决率 + 按月趋势）"""
        # 空库返回零值结构
        empty = models.get_stats()
        self.assertEqual(empty["total"], 0)
        self.assertEqual(empty["solve_rate"], 0.0)
        self.assertEqual(empty["by_category"], [])

        # 构造数据：3 条，分 2 类，2 条已解决
        # （每行只写一条语句：ruff 的 E702 禁止用分号把多条语句挤在一行）
        q1 = models.Question(title="A", category="Bug")
        q2 = models.Question(title="B", category="Bug")
        q2.is_solved = True
        q2.solution = "x"
        q3 = models.Question(title="C", category="文档")
        q3.is_solved = True
        q3.solution = "y"
        models.save_questions([q1, q2, q3])

        s = models.get_stats()
        self.assertEqual(s["total"], 3)
        self.assertEqual(s["solved"], 2)
        self.assertEqual(s["open"], 1)
        self.assertAlmostEqual(s["solve_rate"], 2 / 3)

        # by_category 按总数降序：Bug(2) 在前，文档(1) 在后
        self.assertEqual(len(s["by_category"]), 2)
        bug = s["by_category"][0]
        self.assertEqual(bug["category"], "Bug")
        self.assertEqual(bug["total"], 2)
        self.assertEqual(bug["solved"], 1)
        self.assertEqual(bug["open"], 1)
        doc = s["by_category"][1]
        self.assertEqual(doc["total"], 1)
        self.assertEqual(doc["solved"], 1)

        # by_month 至少有一条，且 total 之和等于总数
        self.assertTrue(len(s["by_month"]) >= 1)
        self.assertEqual(sum(m["total"] for m in s["by_month"]), 3)
        self.assertEqual(sum(m["solved"] for m in s["by_month"]), 2)

    def test_get_stats_corrupt_db(self):
        """数据库损坏时 get_stats 返回零值结构，不抛异常"""
        with open(models.DATA_FILE, 'w', encoding='utf-8') as f:
            f.write("{不是 sqlite 文件")
        s = models.get_stats()
        self.assertEqual(s["total"], 0)
        self.assertEqual(s["by_category"], [])


class TestCLI(QuestionNotebookTestCase):
    """CLI 界面层测试"""

    def test_full_flow(self):
        """完整业务流程：添加→编辑→解决→删除"""
        questions = cli.load_questions()
        self.assertEqual(questions, [])

        with patch('builtins.input', side_effect=["测试问题", "描述", "编程"]):
            cli.add_question(questions)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0].category, "编程")

        with patch('builtins.input', side_effect=["1", "测试问题改", "", ""]):
            cli.edit_question(questions)
        self.assertEqual(questions[0].title, "测试问题改")

        with patch('builtins.input', side_effect=["1", "方案"]):
            cli.solve_question(questions)
        self.assertTrue(questions[0].is_solved)

        with patch('builtins.input', side_effect=["1", "n"]):
            cli.delete_question(questions)  # 取消删除
        self.assertEqual(len(questions), 1)
        with patch('builtins.input', side_effect=["1", "y"]):
            cli.delete_question(questions)  # 确认删除
        self.assertEqual(len(questions), 0)

        self.assertEqual(models.load_questions(), [])

    def test_export_csv(self):
        """CSV 导出：生成文件且带 UTF-8 BOM"""
        questions = [models.Question(title="导出测试", category="测试")]
        models.save_questions(questions)
        cli.export_csv(questions)  # 无 input() 调用，不需要 mock
        files = os.listdir(models.EXPORT_DIR)
        self.assertEqual(len(files), 1)
        with open(os.path.join(models.EXPORT_DIR, files[0]), 'rb') as f:
            self.assertEqual(f.read(3), b'\xef\xbb\xbf')

    def test_backup_restore(self):
        """备份后删除数据，再从备份恢复"""
        questions = [models.Question(title="备份测试")]
        models.save_questions(questions)
        with patch('builtins.input', side_effect=["1", "0"]):
            cli.backup_menu(questions)
        with patch('builtins.input', side_effect=["1", "y"]):
            cli.delete_question(questions)
        self.assertEqual(len(questions), 0)
        with patch('builtins.input', side_effect=["1", "y"]):
            cli.restore_questions(questions)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0].title, "备份测试")

    def test_view_by_category(self):
        """分类浏览：正常选择与无效编号均不崩溃"""
        # 数据必须落盘：view_by_category 开头会 _refresh 从磁盘重载
        questions = [models.Question(title="A", category="编程"),
                     models.Question(title="B")]
        models.save_questions(questions)
        with patch('builtins.input', side_effect=["1"]):
            cli.view_by_category(questions)
        with patch('builtins.input', side_effect=["99"]):
            cli.view_by_category(questions)

    def test_multi_keyword_search(self):
        """多关键词 AND 搜索"""
        # 数据必须落盘：search_questions 开头会 _refresh 从磁盘重载
        questions = [models.Question(title="Python报错", description="编码问题", category="编程"),
                     models.Question(title="电脑卡顿", category="硬件")]
        models.save_questions(questions)
        with patch('builtins.input', side_effect=["Python 编码"]):
            cli.search_questions(questions)  # 应命中第一条
        with patch('builtins.input', side_effect=["Python 硬件"]):
            cli.search_questions(questions)  # 无结果，不崩溃

    def test_refresh_syncs_from_disk(self):
        """_refresh 从磁盘重载：外部写入的数据能同步进内存快照"""
        questions = [models.Question(title="内存数据")]
        models.save_questions(questions)

        # 模拟 Web 端在磁盘上追加了一条（内存快照里没有）
        disk = models.load_questions()
        disk.append(models.Question(title="磁盘新数据"))
        models.save_questions(disk)

        cli._refresh(questions)  # 读操作前的刷新
        titles = [q.title for q in questions]
        self.assertIn("磁盘新数据", titles)
        self.assertEqual(len(questions), 2)


class TestCLIEntryPoint(unittest.TestCase):
    """以子进程方式验证 CLI 入口真的能启动。

    为什么需要这个类：
        此前所有 CLI 测试都是"导入 cli 模块 → 直接调函数"，**从未验证入口本身**。
        也就是说，如果 run_cli.py 的路径引导坏了、或 main() 一启动就崩，
        39 个测试照样全绿，而用户敲 `python run_cli.py` 会直接看到报错。
        这类问题只有"真的把程序跑起来"才能发现。

    注意：本类**不继承** QuestionNotebookTestCase。
        因为子进程不会继承父进程里对 models 路径的内存改写（那只是同一个 Python
        进程内的事），所以数据隔离必须靠环境变量 QUESTION_NOTEBOOK_DATA_DIR
        传给子进程。这正是上一条的实测教训。
    """

    def setUp(self):
        self.tmpdir = _make_test_tmpdir()
        self.env = dict(os.environ)
        self.env["QUESTION_NOTEBOOK_DATA_DIR"] = self.tmpdir
        self.env["PYTHONIOENCODING"] = "utf-8"  # 保证中文输出可被正确解码

    def tearDown(self):
        _remove_tmpdir(self.tmpdir)

    def test_entry_point_starts_and_exits_cleanly(self):
        """python run_cli.py 能启动、打印菜单、并在输入 0 后正常退出（退出码 0）"""
        proc = subprocess.run(
            [sys.executable, "run_cli.py"],
            cwd=PROJECT_ROOT,
            input="0\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self.env,
            timeout=60,
        )
        self.assertEqual(
            proc.returncode, 0,
            f"入口应以退出码 0 结束，实际 {proc.returncode}\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
        self.assertIn(
            "主菜单", proc.stdout,
            f"应打印主菜单。实际输出：\n{proc.stdout}\n{proc.stderr}"
        )
        # 把 stderr 也纳入失败信息，便于定位（例如导入错误会出现在这里）
        self.assertNotIn("Traceback", proc.stderr, f"入口不应抛异常：\n{proc.stderr}")

    def test_entry_point_does_not_touch_real_database(self):
        """入口启动时不得读写项目根目录下真实的 questions.db。

        这是"零安装也能跑"之外的另一条底线：测试无论如何都不能碰到用户真实数据。
        """
        real_db = os.path.join(PROJECT_ROOT, "questions.db")

        def fingerprint():
            if not os.path.exists(real_db):
                return None
            st = os.stat(real_db)
            with open(real_db, "rb") as f:
                return (st.st_size, st.st_mtime, hashlib.sha256(f.read()).hexdigest())

        before = fingerprint()
        proc = subprocess.run(
            [sys.executable, "run_cli.py"],
            cwd=PROJECT_ROOT,
            input="1\n0\n",  # 看一次列表（读操作），再退出
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self.env,
            timeout=60,
        )
        after = fingerprint()

        self.assertEqual(proc.returncode, 0, f"入口异常退出：\n{proc.stderr}")
        self.assertEqual(
            before, after,
            "真实 questions.db 被改动或读取了！测试必须通过 QUESTION_NOTEBOOK_DATA_DIR 完全隔离数据。"
        )


@unittest.skipUnless(HAS_FLASK, "未安装 Flask，跳过 Web 接口测试")
class TestWeb(QuestionNotebookTestCase):
    """Web 接口层测试（Flask test_client，无需启动真实服务）。

    注意：Web 端启用了 CSRF 防护，所有非 GET 请求都要带上 session 里的
    CSRF Token。通过 _open_session() 获取带 token 的客户端后，用
    _csrf_json / _csrf_raw 方法在请求里加上 X-CSRF-Token 头。
    """

    @classmethod
    def setUpClass(cls):
        # 测试环境不设置 QUESTION_NOTEBOOK_PASSWORD：
        # AUTH_ENABLED=False，等价于原有未登录状态下的免登录访问。
        # 用 TESTING=True 关闭 CSRF 的 session-permanent 校验需要的 cookie 行为。
        from question_notebook import web
        web.app.config["TESTING"] = True
        cls.app = web.app
        cls.client = web.app.test_client()

    def setUp(self):
        # 临时目录与数据路径重定向由基类 QuestionNotebookTestCase 统一处理
        super().setUp()
        # 测试客户端：复用 cookies/session，确保 CSRF token 与请求同源
        self.c = self.app.test_client()
        # 先 GET 一次首页或 csrf 接口，建立会话并拿到 CSRF token
        r = self.c.get('/api/csrf')
        self._csrf = r.get_json()["token"]

    # ---------- 带 CSRF 头的请求辅助 ----------

    def _with_csrf(self, kwargs):
        """在请求 headers 中注入 X-CSRF-Token。"""
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("X-CSRF-Token", self._csrf)
        kwargs["headers"] = headers

    def _csrf_get(self, url, **kw):
        return self.c.get(url, **kw)

    def _csrf_json(self, url, payload, method="POST"):
        """发送带 CSRF 头和 JSON body 的请求。
        payload 为 None 表示发送空 body（用于 CSRF 防护校验测试）。"""
        kw = {}
        if payload is None:
            kw["data"] = ""
            kw["content_type"] = "application/json"
        else:
            kw["json"] = payload
        self._with_csrf(kw)
        return self.c.open(url, method=method, **kw)

    def _csrf_put_json(self, url, payload):
        return self._csrf_json(url, payload, method="PUT")

    def _csrf_delete(self, url):
        kw = {}
        self._with_csrf(kw)
        return self.c.delete(url, **kw)

    # ---------- 原有业务测试 ----------

    def test_crud_flow(self):
        """增删改查全链路"""
        r = self._csrf_get('/api/questions')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), [])

        r = self._csrf_json('/api/questions', {"title": "Web测试", "category": "测试"})
        self.assertEqual(r.status_code, 201)
        qid = r.get_json()["id"]
        self.assertEqual(len(self._csrf_get('/api/questions').get_json()), 1)

        r = self._csrf_put_json(f'/api/questions/{qid}',
                                {"is_solved": True, "solution": "方案"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["is_solved"])

        r = self._csrf_delete(f'/api/questions/{qid}')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self._csrf_get('/api/questions').get_json(), [])

    def test_bad_bodies(self):
        """空 body / 非对象 JSON 一律 400"""
        r = self.c.post('/api/questions', data='',
                        content_type='application/json',
                        headers={'X-CSRF-Token': self._csrf})
        self.assertEqual(r.status_code, 400)
        for bad in ([1, 2, 3], "abc", 123):
            r = self._csrf_json('/api/questions', bad)
            self.assertEqual(r.status_code, 400, f"body={bad!r}")
            self.assertIn("error", r.get_json())

    def test_empty_title(self):
        """标题为空返回 400"""
        r = self._csrf_json('/api/questions', {"title": "   "})
        self.assertEqual(r.status_code, 400)

    def test_is_solved_type_check(self):
        """is_solved 必须是布尔：字符串 'false' 应被拒绝"""
        r = self._csrf_json('/api/questions', {"title": "布尔测试"})
        qid = r.get_json()["id"]
        r = self._csrf_put_json(f'/api/questions/{qid}', {"is_solved": "false"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("布尔", r.get_json()["error"])
        r = self._csrf_put_json(f'/api/questions/{qid}', {"is_solved": False})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["is_solved"])

    def test_not_found(self):
        """不存在的 ID 返回 404"""
        self.assertEqual(self._csrf_put_json('/api/questions/999',
                                             {"title": "x"}).status_code, 404)
        self.assertEqual(self._csrf_delete('/api/questions/999').status_code, 404)

    def test_export_csv(self):
        """CSV 导出：200 + BOM"""
        self._csrf_json('/api/questions', {"title": "导出"})
        r = self._csrf_get('/api/export')
        self.assertEqual(r.status_code, 200)
        self.assertIn('text/csv', r.content_type)
        self.assertTrue(r.data.startswith(b'\xef\xbb\xbf'))

    def test_stats_endpoint(self):
        """/api/stats 返回聚合统计，且随数据变化实时更新"""
        # 空库：返回零值
        r = self._csrf_get('/api/stats')
        self.assertEqual(r.status_code, 200)
        s = r.get_json()
        self.assertEqual(s["total"], 0)
        self.assertEqual(s["by_category"], [])

        # 添加 2 条（1 已解决），统计随之变化
        self._csrf_json('/api/questions', {"title": "Bug1", "category": "Bug"})
        # 标记其中一条已解决
        qs = self._csrf_get('/api/questions').get_json()
        qid = qs[0]["id"]
        self._csrf_put_json(f'/api/questions/{qid}', {"is_solved": True, "solution": "搞定"})
        self._csrf_json('/api/questions', {"title": "文档1", "category": "文档"})

        s = self._csrf_get('/api/stats').get_json()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["solved"], 1)
        self.assertEqual(s["open"], 1)
        self.assertAlmostEqual(s["solve_rate"], 0.5)
        # by_category 按总数降序；两类各 1 条，顺序由次排序键 category 决定
        self.assertEqual(len(s["by_category"]), 2)
        self.assertEqual({c["category"] for c in s["by_category"]}, {"Bug", "文档"})

    def test_backup_restore_flow(self):
        """备份 → 清空 → 恢复 全链路"""
        self._csrf_json('/api/questions', {"title": "备份前"})
        r = self._csrf_json('/api/backup', {})
        self.assertEqual(r.status_code, 200)
        filename = r.get_json()["filename"]

        for q in self._csrf_get('/api/questions').get_json():
            self._csrf_delete(f"/api/questions/{q['id']}")
        self.assertEqual(self._csrf_get('/api/questions').get_json(), [])

        r = self._csrf_json('/api/restore', {"filename": filename})
        self.assertEqual(r.status_code, 200)
        data = self._csrf_get('/api/questions').get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "备份前")

    def test_restore_rejects_bad_names(self):
        """恢复接口拒绝非法文件名（路径穿越/前缀不符）"""
        for bad in ("../questions.json", "evil.json", "questions.json"):
            r = self._csrf_json('/api/restore', {"filename": bad})
            self.assertEqual(r.status_code, 400, f"应拒绝 {bad}")

    def test_backups_empty(self):
        """无备份时返回空列表"""
        r = self._csrf_get('/api/backups')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), [])

    # ---------- 新增：CSRF 安全测试 ----------

    def test_csrf_required_for_post(self):
        """POST 不携带 CSRF 头应被 403 拒绝"""
        # 新客户端：带 cookie（有 session）但不带 CSRF 头
        c2 = self.app.test_client()
        c2.get('/api/csrf')  # 建立 session
        r = c2.post('/api/questions', json={"title": "无CSRF测试"})
        self.assertEqual(r.status_code, 403)
        self.assertIn("CSRF", r.get_json()["error"])

    def test_csrf_required_for_put_delete(self):
        """PUT/DELETE 同样要求 CSRF 头"""
        r = self._csrf_json('/api/questions', {"title": "X"})
        qid = r.get_json()["id"]
        # 无 CSRF 头的请求
        self.assertEqual(self.c.put(f'/api/questions/{qid}',
                                    json={"title": "Y"}).status_code, 403)
        self.assertEqual(self.c.delete(f'/api/questions/{qid}').status_code, 403)

    def test_csrf_wrong_token_rejected(self):
        """CSRF 头与会话不一致应被 403 拒绝"""
        r = self.c.post('/api/questions', json={"title": "错token"},
                        headers={"X-CSRF-Token": "not-the-right-token"})
        self.assertEqual(r.status_code, 403)

    def test_login_endpoint_exempt_from_csrf(self):
        """/api/login 是登录前调用的，不做 CSRF 校验（400/401 正常错误）"""
        # 直接 POST 无 CSRF 头：不应是 403，应是密码错误 401（认证开启）或
        # 400（认证关闭需要 JSON 对象 body 也通过；认证关闭 auth=False 直接 200）
        r = self.c.post('/api/login', json={"password": "wrong"})
        self.assertNotEqual(r.status_code, 403)

    def test_csrf_token_issued(self):
        """GET /api/csrf 返回有效 token（每次会话一致）"""
        t1 = self._csrf_get('/api/csrf').get_json()["token"]
        t2 = self._csrf_get('/api/csrf').get_json()["token"]
        self.assertTrue(t1)
        self.assertEqual(t1, t2)  # 同一会话 token 不变

    # ---------- 新增：认证测试（用环境变量临时启用密码）----------

    def test_auth_disabled_by_default(self):
        """默认未设置 QUESTION_NOTEBOOK_PASSWORD → AUTH_ENABLED=False，
        所有接口直接可访问（无需登录）"""
        from question_notebook import web
        self.assertFalse(web.AUTH_ENABLED)
        self.assertEqual(self._csrf_get('/api/auth-status').get_json(),
                         {"auth_enabled": False, "logged_in": True})

    def test_auth_enabled_requires_login(self):
        """启用认证后，受保护接口在未登录时返回 401，登录后恢复访问"""
        from question_notebook import web
        # 临时启用一个密码
        old_enabled = web.AUTH_ENABLED
        old_salt = web._AUTH_SALT
        old_hash = web._AUTH_HASH
        try:
            import hashlib
            web.AUTH_ENABLED = True
            web._AUTH_SALT = b'\x00' * 16
            web._AUTH_HASH = hashlib.pbkdf2_hmac(
                "sha256", "hunter2".encode("utf-8"), web._AUTH_SALT, 100_000
            )
            c = self.app.test_client()
            c.get('/api/csrf')  # 建立会话（拿到 CSRF 与 session）
            with c.session_transaction() as sess:
                csrf = sess["_csrf_token"]
            # 未登录：被 401 拦截
            r = c.get('/api/questions', headers={"X-CSRF-Token": csrf})
            self.assertEqual(r.status_code, 401)
            # 密码错误
            r = c.post('/api/login', json={"password": "wrong"})
            self.assertEqual(r.status_code, 401)
            # 密码正确
            r = c.post('/api/login', json={"password": "hunter2"})
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.get_json()["ok"])
            self.assertIn("token", r.get_json())
            # 登录后刷新会话中的 token（登录成功返回了新 token）
            new_csrf = r.get_json()["token"]
            r = c.get('/api/questions', headers={"X-CSRF-Token": new_csrf})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.get_json(), [])
        finally:
            web.AUTH_ENABLED = old_enabled
            web._AUTH_SALT = old_salt
            web._AUTH_HASH = old_hash

    def test_logout_clears_session(self):
        """登出后再访问受保护接口，认证启用时应重新被 401"""
        from question_notebook import web
        old_enabled = web.AUTH_ENABLED
        old_salt = web._AUTH_SALT
        old_hash = web._AUTH_HASH
        try:
            import hashlib
            web.AUTH_ENABLED = True
            web._AUTH_SALT = b'\x01' * 16
            web._AUTH_HASH = hashlib.pbkdf2_hmac(
                "sha256", "pass1".encode("utf-8"), web._AUTH_SALT, 100_000
            )
            c = self.app.test_client()
            c.get('/api/csrf')
            with c.session_transaction() as sess:
                csrf_before = sess["_csrf_token"]
            r = c.post('/api/login', json={"password": "pass1"})
            self.assertEqual(r.status_code, 200)
            csrf = r.get_json()["token"]
            # 登录会清空并重建会话，因此 CSRF token 必须换新——
            # 若新旧相同，说明会话未重置，存在会话固定（session fixation）风险。
            self.assertNotEqual(csrf, csrf_before)
            # 登出
            r = c.post('/api/logout', headers={"X-CSRF-Token": csrf})
            self.assertEqual(r.status_code, 200)
            # 登出后旧 token 已无效（session 被清空）
            r = c.get('/api/questions', headers={"X-CSRF-Token": csrf})
            self.assertEqual(r.status_code, 401)
        finally:
            web.AUTH_ENABLED = old_enabled
            web._AUTH_SALT = old_salt
            web._AUTH_HASH = old_hash

    def test_login_empty_body_is_400(self):
        """登录接口：非法 body（空/非对象）返回 400，且不应被 CSRF 挡住成 403。
        仅在认证开启场景下校验（auth=False 时登录接口直接返回成功，不校验 body）。"""
        import hashlib

        from question_notebook import web
        old = (web.AUTH_ENABLED, web._AUTH_SALT, web._AUTH_HASH)
        try:
            web.AUTH_ENABLED = True
            web._AUTH_SALT = b'\x02' * 16
            web._AUTH_HASH = hashlib.pbkdf2_hmac(
                "sha256", b"x", web._AUTH_SALT, 100_000
            )
            c = self.app.test_client()
            # 非对象 body：不应是 CSRF 403，而应由 JSON 校验返回 400
            r = c.post('/api/login', json=[1, 2, 3])
            self.assertEqual(r.status_code, 400)
            # 空 body：同样返回 400（而不是 CSRF 错误）
            r = c.post('/api/login', data='', content_type='application/json')
            self.assertEqual(r.status_code, 400)
        finally:
            web.AUTH_ENABLED, web._AUTH_SALT, web._AUTH_HASH = old


if __name__ == "__main__":
    # 直接运行 python tests/test_question_notebook.py 时，用一个自定义 Runner 把结果压成一行，
    # 避免 unittest 默认的 "...." 点阵输出让人看不清最终结论。
    _runner = unittest.TextTestRunner(verbosity=2, buffer=False)
    _result = _runner.run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    print(f"\n{'=' * 60}")
    print(f"测试结果：共 {_result.testsRun} 项 | "
          f"通过 {_result.testsRun - len(_result.failures) - len(_result.errors)} 项 | "
          f"失败 {len(_result.failures)} 项 | 错误 {len(_result.errors)} 项 | "
          f"跳过 {len(_result.skipped)} 项")
    print("=" * 60)
    sys.exit(0 if _result.wasSuccessful() else 1)

