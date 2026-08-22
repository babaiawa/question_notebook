-- ============================================================
-- Question Notebook · SQLite 表结构
-- 版本: v0.2.0
-- 说明: 替换 questions.json 文件存储，字段与 Question 模型(models.py)一一对应。
--       界面层（CLI/Web）零改动，仅 models.py 内部切换实现。
-- ============================================================

-- 启用外键约束（后续 v0.3.0 社区化会引入关联表）
PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- 问题主表：questions
-- 字段对照 Question 模型：
--   id          <- Question.id          （保留原 JSON 中的自增 ID）
--   title       <- Question.title
--   description <- Question.description
--   timestamp   <- Question.timestamp   （格式 YYYY-MM-DD HH:MM:SS，字典序即可排序）
--   is_solved   <- Question.is_solved   （SQLite 无布尔型，用 0/1 + CHECK 约束）
--   solution    <- Question.solution
--   category    <- Question.category
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY,                  -- 问题 ID（允许显式插入以保留历史 ID）
    title       TEXT    NOT NULL,                     -- 问题标题（必填）
    description TEXT    NOT NULL DEFAULT '',          -- 问题描述
    timestamp   TEXT    NOT NULL,                     -- 创建时间，字符串格式便于排序与兼容
    is_solved   INTEGER NOT NULL DEFAULT 0            -- 0=未解决, 1=已解决
                CHECK (is_solved IN (0, 1)),
    solution    TEXT    NOT NULL DEFAULT '',          -- 解决方案
    category    TEXT    NOT NULL DEFAULT '未分类'      -- 分类
);

-- ------------------------------------------------------------
-- 索引：支撑常见查询与后续数据可视化(v0.2.0)场景
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_questions_category  ON questions(category);    -- 按分类筛选 / 分类分布图
CREATE INDEX IF NOT EXISTS idx_questions_is_solved ON questions(is_solved);   -- 按状态筛选 / 解决率统计
CREATE INDEX IF NOT EXISTS idx_questions_timestamp ON questions(timestamp);   -- 按时间排序 / 时间趋势图

-- ------------------------------------------------------------
-- 元数据表：记录 schema 版本与迁移信息，便于后续版本升级
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('schema_version', '0.2.0');
INSERT OR IGNORE INTO schema_meta (key, value) VALUES ('migrated_at',    strftime('%Y-%m-%d %H:%M:%S', 'now', 'localtime'));
