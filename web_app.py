# -*- coding: utf-8 -*-
"""
web_app.py - Web 界面层

负责 Flask 路由和 HTTP 交互，数据逻辑由 models.py 提供。
运行：python web_app.py  →  浏览器打开 http://127.0.0.1:5000

安全机制（可配置）：
- 密码认证：设置环境变量 QUESTION_NOTEBOOK_PASSWORD 后启用登录，
  未设密码时保持免登录（兼容单机使用场景）。
- CSRF 防护：所有非 GET 请求需携带 X-CSRF-Token 请求头，Token 由
  服务端在会话中生成并通过 /api/csrf 获取，或由首页模板下发。
"""
import datetime
import hashlib
import io
import os
import secrets
from functools import wraps

from flask import (
    Flask, request, jsonify, render_template,
    send_file, session, abort,
)

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
app.json.ensure_ascii = False  # 中文原样输出，不做 \uXXXX 转义

# ---------- 安全配置 ----------

# Flask 会话签名密钥：优先用环境变量，否则用文件内持久化密钥
_ENV_SECRET = os.environ.get("QUESTION_NOTEBOOK_SECRET")
_SECRET_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".flask_secret"
)
if _ENV_SECRET:
    app.secret_key = _ENV_SECRET
else:
    if not os.path.exists(_SECRET_FILE):
        # 首次运行生成持久密钥并保存（重启后登录会话仍有效）
        with open(_SECRET_FILE, "w", encoding="utf-8") as _f:
            _f.write(secrets.token_hex(32))
    with open(_SECRET_FILE, "r", encoding="utf-8") as _f:
        app.secret_key = _f.read().strip()

# 密码：未设置时免登录（兼容单机 127.0.0.1 使用）
_AUTH_PASSWORD = os.environ.get("QUESTION_NOTEBOOK_PASSWORD", "").strip()
AUTH_ENABLED = bool(_AUTH_PASSWORD)

# 密码哈希：不做明文比较，用 stdlib pbkdf2_hmac（SHA-256, 10 万次迭代）
_AUTH_SALT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".auth_salt"
)
if AUTH_ENABLED:
    if not os.path.exists(_AUTH_SALT_FILE):
        with open(_AUTH_SALT_FILE, "w", encoding="utf-8") as _f:
            _f.write(secrets.token_hex(16))
    with open(_AUTH_SALT_FILE, "r", encoding="utf-8") as _f:
        _AUTH_SALT = bytes.fromhex(_f.read().strip())
    _AUTH_HASH = hashlib.pbkdf2_hmac(
        "sha256", _AUTH_PASSWORD.encode("utf-8"), _AUTH_SALT, 100_000
    )
else:
    _AUTH_SALT = None
    _AUTH_HASH = None

# 清理明文引用，避免意外泄漏
del _AUTH_PASSWORD


def _password_verify(password: str) -> bool:
    """用 PBKDF2 校验密码，防时序攻击（hmac.compare_digest）。"""
    if not AUTH_ENABLED:
        return True
    import hmac
    d = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), _AUTH_SALT, 100_000
    )
    return hmac.compare_digest(d, _AUTH_HASH)


def _require_auth(view_func):
    """装饰器：认证开启时要求已登录，否则返回 401。"""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if AUTH_ENABLED and not session.get("logged_in"):
            return jsonify({"error": "未登录"}), 401
        return view_func(*args, **kwargs)
    return wrapper


# ---------- CSRF ----------

CSRF_HEADER = "X-CSRF-Token"
_CSRF_SESSION_KEY = "_csrf_token"


def _ensure_csrf_token() -> str:
    """获取当前会话的 CSRF Token，不存在则生成一个。"""
    token = session.get(_CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[_CSRF_SESSION_KEY] = token
    return token


def _validate_csrf(view_func):
    """装饰器：非 GET/HEAD/OPTIONS 请求需携带合法 CSRF Token。
    认证未启用时仍强制校验（防止第三方站点伪造请求）。"""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return view_func(*args, **kwargs)
        expected = session.get(_CSRF_SESSION_KEY)
        received = request.headers.get(CSRF_HEADER)
        import hmac
        if not expected or not received or not hmac.compare_digest(expected, received):
            return jsonify({"error": "CSRF 校验失败"}), 403
        return view_func(*args, **kwargs)
    return wrapper


# 为所有非 GET 路由强制启用 CSRF 校验
@app.before_request
def _csrf_protection():
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    expected = session.get(_CSRF_SESSION_KEY)
    received = request.headers.get(CSRF_HEADER)
    import hmac
    if not expected or not received or not hmac.compare_digest(expected, received):
        # 登录接口除外：未登录前没有 session，也就没有 token
        if request.path == "/api/login" and request.method == "POST":
            return
        return jsonify({"error": "CSRF 校验失败"}), 403


# ---------- 公共 ----------

def _get_json_body():
    """安全解析请求体：空 body / 非 JSON / 非对象时返回 None，由调用方返回友好错误。"""
    data = request.get_json(force=True, silent=True)
    # 只接受 JSON 对象（dict）；数组/字符串等非对象会让后续 .get() 崩溃
    if not isinstance(data, dict):
        return None
    return data


# ---------- 认证 / CSRF API ----------

@app.route('/api/csrf', methods=['GET'])
def api_csrf():
    """下发当前会话的 CSRF Token。未启用认证时也返回一个，便于前端统一处理。"""
    return jsonify({"token": _ensure_csrf_token()})


@app.route('/api/login', methods=['POST'])
def api_login():
    """登录：校验密码，写入 session，下发 CSRF Token。"""
    if not AUTH_ENABLED:
        # 免登录模式仍返回 200 + token，便于前端共用同一套流程
        return jsonify({"ok": True, "token": _ensure_csrf_token(), "auth": False})
    data = _get_json_body()
    if data is None:
        return jsonify({"error": "请求体必须是 JSON"}), 400
    password = data.get("password", "")
    if not isinstance(password, str) or not _password_verify(password):
        return jsonify({"error": "密码错误"}), 401
    session.clear()
    session["logged_in"] = True
    return jsonify({"ok": True, "token": _ensure_csrf_token(), "auth": True})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    """登出：清空 session。"""
    session.clear()
    return jsonify({"ok": True})


@app.route('/api/auth-status')
def api_auth_status():
    """返回认证启用状态与当前登录态，用于页面首次加载判断是否跳登录页。"""
    return jsonify({
        "auth_enabled": AUTH_ENABLED,
        "logged_in": bool(session.get("logged_in")) if AUTH_ENABLED else True,
    })


# ---------- 页面 ----------

@app.route('/')
def index():
    # 渲染模板时把 CSRF Token 和认证状态一并注入，减少前端一次请求
    return render_template(
        'index.html',
        csrf_token=_ensure_csrf_token(),
        auth_enabled="true" if AUTH_ENABLED else "false",
        logged_in="true" if (not AUTH_ENABLED or session.get("logged_in")) else "false",
    )


# ---------- 问题 API ----------

@app.route('/api/questions')
@_require_auth
def api_list():
    """获取全部问题。"""
    questions = load_questions()
    return jsonify([q.to_dict() for q in questions])


@app.route('/api/questions', methods=['POST'])
@_require_auth
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
@_require_auth
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
@_require_auth
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
@_require_auth
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
@_require_auth
def api_backup():
    """一键备份到 backups/ 目录（带时间戳）。"""
    with data_lock():
        name = backup_data()
    if name is None:
        return jsonify({"error": "没有数据可备份"}), 400
    return jsonify({"ok": True, "filename": name})


@app.route('/api/backups')
@_require_auth
def api_backups():
    """列出所有备份文件（新的在前）。"""
    return jsonify(list_backups())


@app.route('/api/restore', methods=['POST'])
@_require_auth
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
    if AUTH_ENABLED:
        print("认证已启用（登录密码来自 QUESTION_NOTEBOOK_PASSWORD 环境变量）")
    else:
        print("提示：未设置 QUESTION_NOTEBOOK_PASSWORD，认证未启用（仅本机访问）")
        print("  局域网部署前请设置密码：QUESTION_NOTEBOOK_PASSWORD=你的密码 python web_app.py")
    print("按 Ctrl+C 停止服务")
    app.run(debug=False, host='127.0.0.1', port=5000)
