# -*- coding: utf-8 -*-
"""
test_qn.py - Question Notebook 自动化测试

运行：python test_qn.py

覆盖范围：
- 数据层（models）：模型序列化往返、读写循环、旧数据兼容、损坏文件容错
- CLI 层：完整业务流程、备份恢复、CSV 导出、分类浏览、多关键词搜索

安全说明：测试会将数据文件重定向到临时目录，不会读写真实的 questions.json。
"""
import os
import sys
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models
import question_notebook as cli

# 检测 Flask 是否可用：未安装时跳过 Web 接口测试，数据层/CLI 测试照常运行
try:
    import flask  # noqa: F401
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False


class TestModels(unittest.TestCase):
    """数据层测试"""

    def setUp(self):
        # 数据重定向到临时目录，隔离真实数据。
        # CLI/Web 通过 models.X 动态访问路径常量（见 #7 重构），
        # 因此只需改 models 一处，无需再同步 cli/web。
        self.tmpdir = tempfile.mkdtemp(prefix="qn_test_")
        models.BASE_DIR = self.tmpdir
        models.DATA_FILE = os.path.join(self.tmpdir, "questions.json")
        models.BACKUP_DIR = os.path.join(self.tmpdir, "backups")
        models.EXPORT_DIR = os.path.join(self.tmpdir, "exports")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

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

    def test_old_data_compat(self):
        """缺失 category 字段的历史数据自动补默认值"""
        old = [{"id": 1, "title": "旧问题", "description": "",
                "timestamp": "", "is_solved": False, "solution": ""}]
        with open(models.DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(old, f, ensure_ascii=False)
        loaded = models.load_questions()
        self.assertEqual(loaded[0].category, models.DEFAULT_CATEGORY)

    def test_corrupt_json(self):
        """损坏的 JSON 文件：备份 .bak 后返回空列表，不崩溃"""
        with open(models.DATA_FILE, 'w', encoding='utf-8') as f:
            f.write("{损坏的JSON")
        loaded = models.load_questions()
        self.assertEqual(loaded, [])
        self.assertTrue(os.path.exists(models.DATA_FILE + ".bak"))

    def test_wrong_top_level_type(self):
        """合法 JSON 但顶层不是数组（对象/字符串）：按损坏处理，不崩溃"""
        for bad in ('{"a": 1}', '"just a string"', "123"):
            # 每个用例前清掉上次的 .bak
            if os.path.exists(models.DATA_FILE + ".bak"):
                os.remove(models.DATA_FILE + ".bak")
            with open(models.DATA_FILE, 'w', encoding='utf-8') as f:
                f.write(bad)
            loaded = models.load_questions()
            self.assertEqual(loaded, [], f"顶层为 {bad[:20]} 时应返回空列表")
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

    def test_trailing_newline(self):
        """数据文件末尾有换行（避免 git diff 噪音）"""
        questions = [models.Question(title="换行测试")]
        models.save_questions(questions)
        with open(models.DATA_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertTrue(content.endswith('\n'))

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


class TestCLI(unittest.TestCase):
    """CLI 界面层测试"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="qn_test_")
        models.BASE_DIR = self.tmpdir
        models.DATA_FILE = os.path.join(self.tmpdir, "questions.json")
        models.BACKUP_DIR = os.path.join(self.tmpdir, "backups")
        models.EXPORT_DIR = os.path.join(self.tmpdir, "exports")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

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


@unittest.skipUnless(HAS_FLASK, "未安装 Flask，跳过 Web 接口测试")
class TestWeb(unittest.TestCase):
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
        import web_app
        web_app.app.config["TESTING"] = True
        cls.app = web_app.app
        cls.client = web_app.app.test_client()

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="qn_test_")
        models.BASE_DIR = self.tmpdir
        models.DATA_FILE = os.path.join(self.tmpdir, "questions.json")
        models.BACKUP_DIR = os.path.join(self.tmpdir, "backups")
        models.EXPORT_DIR = os.path.join(self.tmpdir, "exports")
        # 测试客户端：复用 cookies/session，确保 CSRF token 与请求同源
        self.c = self.app.test_client()
        # 先 GET 一次首页或 csrf 接口，建立会话并拿到 CSRF token
        r = self.c.get('/api/csrf')
        self._csrf = r.get_json()["token"]

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

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
        import web_app
        self.assertFalse(web_app.AUTH_ENABLED)
        self.assertEqual(self._csrf_get('/api/auth-status').get_json(),
                         {"auth_enabled": False, "logged_in": True})

    def test_auth_enabled_requires_login(self):
        """启用认证后，受保护接口在未登录时返回 401，登录后恢复访问"""
        import web_app
        # 临时启用一个密码
        old_enabled = web_app.AUTH_ENABLED
        old_salt = web_app._AUTH_SALT
        old_hash = web_app._AUTH_HASH
        try:
            import hashlib
            web_app.AUTH_ENABLED = True
            web_app._AUTH_SALT = b'\x00' * 16
            web_app._AUTH_HASH = hashlib.pbkdf2_hmac(
                "sha256", "hunter2".encode("utf-8"), web_app._AUTH_SALT, 100_000
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
            web_app.AUTH_ENABLED = old_enabled
            web_app._AUTH_SALT = old_salt
            web_app._AUTH_HASH = old_hash

    def test_logout_clears_session(self):
        """登出后再访问受保护接口，认证启用时应重新被 401"""
        import web_app
        old_enabled = web_app.AUTH_ENABLED
        old_salt = web_app._AUTH_SALT
        old_hash = web_app._AUTH_HASH
        try:
            import hashlib
            web_app.AUTH_ENABLED = True
            web_app._AUTH_SALT = b'\x01' * 16
            web_app._AUTH_HASH = hashlib.pbkdf2_hmac(
                "sha256", "pass1".encode("utf-8"), web_app._AUTH_SALT, 100_000
            )
            c = self.app.test_client()
            c.get('/api/csrf')
            with c.session_transaction() as sess:
                csrf_before = sess["_csrf_token"]
            r = c.post('/api/login', json={"password": "pass1"})
            self.assertEqual(r.status_code, 200)
            csrf = r.get_json()["token"]
            # 登出
            r = c.post('/api/logout', headers={"X-CSRF-Token": csrf})
            self.assertEqual(r.status_code, 200)
            # 登出后旧 token 已无效（session 被清空）
            r = c.get('/api/questions', headers={"X-CSRF-Token": csrf})
            self.assertEqual(r.status_code, 401)
        finally:
            web_app.AUTH_ENABLED = old_enabled
            web_app._AUTH_SALT = old_salt
            web_app._AUTH_HASH = old_hash

    def test_login_empty_body_is_400(self):
        """登录接口：非法 body（空/非对象）返回 400，且不应被 CSRF 挡住成 403。
        仅在认证开启场景下校验（auth=False 时登录接口直接返回成功，不校验 body）。"""
        import web_app, hashlib
        old = (web_app.AUTH_ENABLED, web_app._AUTH_SALT, web_app._AUTH_HASH)
        try:
            web_app.AUTH_ENABLED = True
            web_app._AUTH_SALT = b'\x02' * 16
            web_app._AUTH_HASH = hashlib.pbkdf2_hmac(
                "sha256", b"x", web_app._AUTH_SALT, 100_000
            )
            c = self.app.test_client()
            # 非对象 body：不应是 CSRF 403，而应由 JSON 校验返回 400
            r = c.post('/api/login', json=[1, 2, 3])
            self.assertEqual(r.status_code, 400)
            # 空 body：同样返回 400（而不是 CSRF 错误）
            r = c.post('/api/login', data='', content_type='application/json')
            self.assertEqual(r.status_code, 400)
        finally:
            web_app.AUTH_ENABLED, web_app._AUTH_SALT, web_app._AUTH_HASH = old


if __name__ == "__main__":
    unittest.main(verbosity=2)

