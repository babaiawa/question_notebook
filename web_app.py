# -*- coding: utf-8 -*-
"""
问题笔记本 Web 版（Flask）
- 与 CLI 版共用同一个 questions.json，数据完全互通
- 运行：python web_app.py  →  浏览器打开 http://127.0.0.1:5000
"""
import json
import os
import csv
import io
import datetime
import shutil

from flask import Flask, request, jsonify, render_template, send_file

# 复用 CLI 版的 Question 类和路径常量（import 不会触发 CLI 的 main()）
import question_notebook as qn

app = Flask(__name__)
# 让 JSON 响应里的中文原样输出，而不是 \uXXXX 转义
app.json.ensure_ascii = False


# ---------- 数据读写（与 CLI 版格式一致） ----------

def load_data():
    """读取 questions.json，返回 Question 对象列表。"""
    if not os.path.exists(qn.DATA_FILE):
        return []
    with open(qn.DATA_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    questions = []
    for item in data:
        q = qn.Question(
            title=item.get('title', ''),
            description=item.get('description', ''),
            is_solved=item.get('is_solved', False),
            solution=item.get('solution', ''),
            category=item.get('category', qn.DEFAULT_CATEGORY)
        )
        q.id = item.get('id')
        q.timestamp = item.get('timestamp', '')
        questions.append(q)
    return questions


def save_data(questions):
    """将 Question 对象列表写入 questions.json（新问题自动分配 ID）。"""
    max_id = 0
    for q in questions:
        if q.id is not None and q.id > max_id:
            max_id = q.id

    items = []
    for q in questions:
        if q.id is None:
            max_id += 1
            q.id = max_id
        items.append({
            "id": q.id,
            "title": q.title,
            "description": q.description,
            "timestamp": q.timestamp,
            "is_solved": q.is_solved,
            "solution": q.solution,
            "category": q.category
        })

    with open(qn.DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, indent=4, ensure_ascii=False)


def to_dict(q):
    """Question 对象转成 JSON 可序列化的字典。"""
    return {
        "id": q.id,
        "title": q.title,
        "description": q.description,
        "timestamp": q.timestamp,
        "is_solved": q.is_solved,
        "solution": q.solution,
        "category": q.category
    }


# ---------- 页面 ----------

@app.route('/')
def index():
    return render_template('index.html')


# ---------- 问题 API ----------

@app.route('/api/questions')
def api_list():
    """获取全部问题。"""
    questions = load_data()
    return jsonify([to_dict(q) for q in questions])


@app.route('/api/questions', methods=['POST'])
def api_add():
    """添加问题。body: {title, description, category}"""
    data = request.get_json(force=True)
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({"error": "标题不能为空"}), 400

    q = qn.Question(
        title=title,
        description=(data.get('description') or '').strip(),
        category=(data.get('category') or '').strip() or qn.DEFAULT_CATEGORY
    )
    questions = load_data()
    questions.append(q)
    save_data(questions)
    return jsonify(to_dict(q)), 201


@app.route('/api/questions/<int:qid>', methods=['PUT'])
def api_update(qid):
    """编辑问题（也可用于标记已解决）。body 里带哪个字段就改哪个。"""
    data = request.get_json(force=True)
    questions = load_data()
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
                q.is_solved = bool(data.get('is_solved'))
            if 'solution' in data:
                q.solution = (data.get('solution') or '').strip()
            save_data(questions)
            return jsonify(to_dict(q))
    return jsonify({"error": "未找到该问题"}), 404


@app.route('/api/questions/<int:qid>', methods=['DELETE'])
def api_delete(qid):
    """删除问题。"""
    questions = load_data()
    new_list = [q for q in questions if q.id != qid]
    if len(new_list) == len(questions):
        return jsonify({"error": "未找到该问题"}), 404
    save_data(new_list)
    return jsonify({"ok": True})


# ---------- 导出 / 备份 / 恢复 ----------

@app.route('/api/export')
def api_export():
    """导出 CSV（UTF-8 BOM，Excel 打开不乱码）。"""
    questions = load_data()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "标题", "描述", "创建时间", "是否已解决", "解决方案", "分类"])
    for q in questions:
        writer.writerow([
            q.id, q.title, q.description, q.timestamp,
            "是" if q.is_solved else "否", q.solution, q.category
        ])
    # 加 BOM 头，Excel 才能正确识别 UTF-8
    data = ('\ufeff' + output.getvalue()).encode('utf-8')
    filename = f'questions_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    return send_file(
        io.BytesIO(data),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )


@app.route('/api/backup', methods=['POST'])
def api_backup():
    """一键备份到 backups/ 目录（带时间戳）。"""
    if not os.path.exists(qn.DATA_FILE):
        return jsonify({"error": "没有数据可备份"}), 400
    os.makedirs(qn.BACKUP_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"questions_{ts}.json"
    shutil.copy2(qn.DATA_FILE, os.path.join(qn.BACKUP_DIR, name))
    return jsonify({"ok": True, "filename": name})


@app.route('/api/backups')
def api_backups():
    """列出所有备份文件（新的在前）。"""
    if not os.path.isdir(qn.BACKUP_DIR):
        return jsonify([])
    files = sorted(
        [f for f in os.listdir(qn.BACKUP_DIR)
         if f.startswith("questions_") and f.endswith(".json")],
        reverse=True
    )
    return jsonify(files)


@app.route('/api/restore', methods=['POST'])
def api_restore():
    """从备份恢复。body: {filename}（做了路径穿越防护）。"""
    data = request.get_json(force=True)
    name = data.get('filename', '')
    # 防路径穿越：只允许纯文件名
    if not name or '/' in name or '\\' in name:
        return jsonify({"error": "无效的备份文件名"}), 400
    backup_path = os.path.join(qn.BACKUP_DIR, name)
    if not os.path.exists(backup_path):
        return jsonify({"error": "备份文件不存在"}), 404
    shutil.copy2(backup_path, qn.DATA_FILE)
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("问题笔记本 Web 版已启动：http://127.0.0.1:5000")
    print("按 Ctrl+C 停止服务")
    app.run(debug=False, host='127.0.0.1', port=5000)
