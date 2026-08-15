# -*- coding: utf-8 -*-
"""
web_app.py - Web 界面层

负责 Flask 路由和 HTTP 交互，数据逻辑由 models.py 提供。
运行：python web_app.py  →  浏览器打开 http://127.0.0.1:5000
"""
import datetime
import io

from flask import Flask, request, jsonify, render_template, send_file

# 数据模型与路径常量统一来自数据层 models.py
from models import (
    Question,
    load_questions,
    save_questions,
    build_csv,
    backup_data,
    list_backups,
    restore_data,
    data_lock,
    DEFAULT_CATEGORY,
)

app = Flask(__name__)
# 让 JSON 响应里的中文原样输出，而不是 \uXXXX 转义
app.json.ensure_ascii = False


def _get_json_body():
    """安全解析请求体：空 body / 非 JSON / 非对象时返回 None，由调用方返回友好错误。"""
    data = request.get_json(force=True, silent=True)
    # 只接受 JSON 对象（dict）；数组/字符串等非对象会让后续 .get() 崩溃
    if not isinstance(data, dict):
        return None
    return data


# ---------- 页面 ----------

@app.route('/')
def index():
    return render_template('index.html')


# ---------- 问题 API ----------

@app.route('/api/questions')
def api_list():
    """获取全部问题。"""
    questions = load_questions()
    return jsonify([q.to_dict() for q in questions])


@app.route('/api/questions', methods=['POST'])
def api_add():
    """添加问题。body: {title, description, category}"""
    data = _get_json_body()
    if data is None:
        return jsonify({"error": "请求体必须是 JSON"}), 400
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({"error": "标题不能为空"}), 400

    with data_lock():
        q = Question(
            title=title,
            description=(data.get('description') or '').strip(),
            category=(data.get('category') or '').strip() or DEFAULT_CATEGORY
        )
        questions = load_questions()
        questions.append(q)
        save_questions(questions)
    return jsonify(q.to_dict()), 201


@app.route('/api/questions/<int:qid>', methods=['PUT'])
def api_update(qid):
    """编辑问题（也可用于标记已解决）。body 里带哪个字段就改哪个。"""
    data = _get_json_body()
    if data is None:
        return jsonify({"error": "请求体必须是 JSON"}), 400

    with data_lock():
        questions = load_questions()
        for q in questions:
            if q.id == qid:
                if 'title' in data:
                    title = (data.get('title') or '').strip()
                    if title:
                        q.title = title
                if 'description' in data:
                    q.description = (data.get('description') or '').strip()
                if 'category' in data:
                    cat = (data.get('category') or '').strip()
                    if cat:
                        q.category = cat
                if 'is_solved' in data:
                    # 严格类型校验：字符串 "false" 不能当 True 用
                    if not isinstance(data.get('is_solved'), bool):
                        return jsonify({"error": "is_solved 必须是布尔值"}), 400
                    q.is_solved = data['is_solved']
                if 'solution' in data:
                    q.solution = (data.get('solution') or '').strip()
                save_questions(questions)
                return jsonify(q.to_dict())
    return jsonify({"error": "未找到该问题"}), 404


@app.route('/api/questions/<int:qid>', methods=['DELETE'])
def api_delete(qid):
    """删除问题。"""
    with data_lock():
        questions = load_questions()
        new_list = [q for q in questions if q.id != qid]
        if len(new_list) == len(questions):
            return jsonify({"error": "未找到该问题"}), 404
        save_questions(new_list)
    return jsonify({"ok": True})


# ---------- 导出 / 备份 / 恢复 ----------

@app.route('/api/export')
def api_export():
    """导出 CSV（UTF-8 BOM，Excel 打开不乱码）。"""
    questions = load_questions()
    content = build_csv(questions)
    # 文件名含微秒，同一秒内多次导出不会互相覆盖
    filename = f'questions_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.csv'
    return send_file(
        io.BytesIO(content.encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )


@app.route('/api/backup', methods=['POST'])
def api_backup():
    """一键备份到 backups/ 目录（带时间戳）。"""
    with data_lock():
        name = backup_data()
    if name is None:
        return jsonify({"error": "没有数据可备份"}), 400
    return jsonify({"ok": True, "filename": name})


@app.route('/api/backups')
def api_backups():
    """列出所有备份文件（新的在前）。"""
    return jsonify(list_backups())


@app.route('/api/restore', methods=['POST'])
def api_restore():
    """从备份恢复。body: {filename}（白名单校验，拒绝路径穿越）。"""
    data = _get_json_body()
    if data is None:
        return jsonify({"error": "请求体必须是 JSON"}), 400
    filename = data.get('filename', '')
    with data_lock():
        ok = restore_data(filename)
    if not ok:
        return jsonify({"error": "无效的备份文件名"}), 400
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("问题笔记本 Web 版已启动：http://127.0.0.1:5000")
    print("按 Ctrl+C 停止服务")
    app.run(debug=False, host='127.0.0.1', port=5000)
