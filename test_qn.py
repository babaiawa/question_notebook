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


class TestModels(unittest.TestCase):
    """数据层测试"""

    def setUp(self):
        # 数据重定向到临时目录，隔离真实数据。
        # 注意：cli 模块通过 `from models import ...` 导入常量，是值拷贝，
        # 必须同时更新 models 和 cli 两边的路径，测试才不会碰到真实文件。
        self.tmpdir = tempfile.mkdtemp(prefix="qn_test_")
        tmp_data = os.path.join(self.tmpdir, "questions.json")
        tmp_backup = os.path.join(self.tmpdir, "backups")
        tmp_export = os.path.join(self.tmpdir, "exports")
        models.BASE_DIR = cli.BASE_DIR = self.tmpdir
        models.DATA_FILE = cli.DATA_FILE = tmp_data
        models.BACKUP_DIR = cli.BACKUP_DIR = tmp_backup
        models.EXPORT_DIR = cli.EXPORT_DIR = tmp_export

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
        tmp_data = os.path.join(self.tmpdir, "questions.json")
        tmp_backup = os.path.join(self.tmpdir, "backups")
        tmp_export = os.path.join(self.tmpdir, "exports")
        models.BASE_DIR = cli.BASE_DIR = self.tmpdir
        models.DATA_FILE = cli.DATA_FILE = tmp_data
        models.BACKUP_DIR = cli.BACKUP_DIR = tmp_backup
        models.EXPORT_DIR = cli.EXPORT_DIR = tmp_export

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
        with patch('builtins.input', side_effect=["9"]):
            cli.export_csv(questions)
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
        questions = [models.Question(title="A", category="编程"),
                     models.Question(title="B")]
        with patch('builtins.input', side_effect=["1"]):
            cli.view_by_category(questions)
        with patch('builtins.input', side_effect=["99"]):
            cli.view_by_category(questions)

    def test_multi_keyword_search(self):
        """多关键词 AND 搜索"""
        questions = [models.Question(title="Python报错", description="编码问题", category="编程"),
                     models.Question(title="电脑卡顿", category="硬件")]
        with patch('builtins.input', side_effect=["Python 编码"]):
            cli.search_questions(questions)  # 应命中第一条
        with patch('builtins.input', side_effect=["Python 硬件"]):
            cli.search_questions(questions)  # 无结果，不崩溃


if __name__ == "__main__":
    unittest.main(verbosity=2)

