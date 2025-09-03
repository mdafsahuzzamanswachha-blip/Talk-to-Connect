import os
from datetime import datetime
from uuid import uuid4
from collections import defaultdict

from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from models import db, User, Message, CallLog

load_dotenv()

# -----------------------
# App setup
# -----------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///chat.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "static/uploads")
ALLOWED_EXTENSIONS = set(ext.strip().lower() for ext in os.getenv("ALLOWED_EXTENSIONS", "pdf,doc,docx,jpg,jpeg,png,txt").split(","))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

socketio = SocketIO(app, cors_allowed_origins="*")  # Allow all origins for dev

# Presence tracking
ONLINE = {}  # user_id -> connection count
USER_SIDS = defaultdict(set)  # user_id -> set of sids


def dm_room(a_id: int, b_id: int) -> str:
    a, b = sorted([int(a_id), int(b_id)])
    return f"dm:{a}:{b}"


def call_room(a_id: int, b_id: int) -> str:
    a, b = sorted([int(a_id), int(b_id)])
    return f"call:{a}:{b}"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -----------------------
# Auth pages (HTML)
# -----------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            user.last_seen = datetime.utcnow()
            db.session.commit()
            return redirect(url_for("index"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not email or not username or not password:
            return render_template("register.html", error="All fields are required.")
        if User.query.filter_by(email=email).first():
            return render_template("register.html", error="Email already registered.")
        hashed = generate_password_hash(password)
        user = User(email=email, username=username, password=hashed)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# -----------------------
# Auth APIs (JSON for auth.js)
# -----------------------
@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        login_user(user)
        user.last_seen = datetime.utcnow()
        db.session.commit()
        # Using server-side session cookie via Flask-Login; no JWT returned
        return jsonify({"ok": True, "user_id": user.id, "username": user.username})
    return jsonify({"error": "Invalid credentials"}), 401


@app.route("/api/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"ok": True})


# -----------------------
# App pages
# -----------------------
@app.route("/")
@login_required
def index():
    users = User.query.filter(User.id != current_user.id).order_by(User.username.asc()).all()
    online_ids = set(ONLINE.keys())
    return render_template("index.html", users=users, online_ids=online_ids)


# Optional: /chat route for front-end redirects
@app.route("/chat")
@login_required
def chat_redirect():
    return redirect(url_for("index"))


@app.route("/call/<int:user_id>/<call_type>")
@login_required
def call_page(user_id, call_type):
    if call_type not in ("audio", "video"):
        abort(404)
    peer = User.query.get_or_404(user_id)
    return render_template("call.html", peer=peer, call_type=call_type)


# -----------------------
# API endpoints
# -----------------------
@app.route("/api/messages/<int:other_id>")
@login_required
def api_messages(other_id):
    msgs = (
        Message.query.filter(
            db.or_(
                db.and_(Message.sender_id == current_user.id, Message.receiver_id == other_id),
                db.and_(Message.sender_id == other_id, Message.receiver_id == current_user.id),
            )
        )
        .order_by(Message.created_at.asc())
        .limit(200)
        .all()
    )

    def serialize(m: Message):
        return {
            "id": m.id,
            "sender_id": m.sender_id,
            "receiver_id": m.receiver_id,
            "content": m.content,
            "file_url": m.file_url,
            "created_at": m.created_at.isoformat() + "Z",
        }

    return jsonify([serialize(m) for m in msgs])


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/upload", methods=["POST"])
@login_required
def upload():
    other_id = int(request.form.get("receiver_id", "0"))
    if "file" not in request.files or not other_id:
        return jsonify({"error": "No file or receiver"}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    if not allowed_file(f.filename):
        return jsonify({"error": "File type not allowed"}), 400
    fname = secure_filename(f.filename)
    ext = fname.rsplit(".", 1)[-1].lower()
    new_name = f"{uuid4().hex}.{ext}"
    path = os.path.join(UPLOAD_FOLDER, new_name)
    f.save(path)
    file_url = f"/{path.replace(os.path.sep, '/')}"
    msg = Message(sender_id=current_user.id, receiver_id=other_id, content=None, file_url=file_url)
    db.session.add(msg)
    db.session.commit()
    room = dm_room(current_user.id, other_id)
    payload = {
        "id": msg.id,
        "sender_id": current_user.id,
        "receiver_id": other_id,
        "content": None,
        "file_url": file_url,
        "created_at": msg.created_at.isoformat() + "Z",
    }
    socketio.emit("new_message", payload, room=room)
    # Also emit directly to receiver's sids in case they haven't joined the DM room
    for sid in USER_SIDS.get(other_id, []):
        socketio.emit("new_message", payload, to=sid)
    return jsonify({"ok": True, "message": payload})


@app.route("/api/last_seen/<int:user_id>")
@login_required
def api_last_seen(user_id):
    user = User.query.get_or_404(user_id)
    online = user_id in ONLINE and ONLINE[user_id] > 0
    return jsonify({
        "status": "online" if online else "offline",
        "last_seen": user.last_seen.isoformat() + "Z" if user.last_seen else None
    })


# -----------------------
# Socket.IO events
# -----------------------
@socketio.on("connect")
def on_connect():
    if not current_user.is_authenticated:
        return False
    uid = int(current_user.id)
    ONLINE[uid] = ONLINE.get(uid, 0) + 1
    USER_SIDS[uid].add(request.sid)
    User.query.filter_by(id=uid).update({"last_seen": datetime.utcnow()})
    db.session.commit()
    emit("presence", {"user_id": uid, "status": "online"}, broadcast=True)


@socketio.on("disconnect")
def on_disconnect():
    if not current_user.is_authenticated:
        return
    uid = int(current_user.id)
    # Remove sid mapping
    USER_SIDS[uid].discard(request.sid)
    if not USER_SIDS[uid]:
        USER_SIDS.pop(uid, None)
    # Decrement connection count
    ONLINE[uid] = max(0, ONLINE.get(uid, 1) - 1)
    if ONLINE[uid] == 0:
        ONLINE.pop(uid, None)
        emit("presence", {"user_id": uid, "status": "offline"}, broadcast=True)


@socketio.on("set_online")
def on_set_online(data):
    # Optional event from client after reconnect; presence is already handled in connect
    if not current_user.is_authenticated:
        return
    uid = int(current_user.id)
    ONLINE[uid] = max(ONLINE.get(uid, 0), 1)
    User.query.filter_by(id=uid).update({"last_seen": datetime.utcnow()})
    db.session.commit()
    emit("presence", {"user_id": uid, "status": "online"}, broadcast=True)


@socketio.on("join_dm")
def on_join_dm(data):
    other_id = int(data.get("other_id"))
    room = dm_room(current_user.id, other_id)
    join_room(room)
    emit("joined_dm", {"room": room})


@socketio.on("typing")
def on_typing(data):
    other_id = int(data.get("other_id"))
    is_typing = bool(data.get("typing"))
    room = dm_room(current_user.id, other_id)
    emit("typing", {"from": current_user.id, "typing": is_typing}, room=room, include_self=False)
    # Also target receiver directly in case they aren't in the room
    for sid in USER_SIDS.get(other_id, []):
        socketio.emit("typing", {"from": current_user.id, "typing": is_typing}, to=sid)


@socketio.on("send_message")
def on_send_message(data):
    other_id = int(data.get("other_id"))
    text = (data.get("content") or "").strip()
    if not text and not data.get("file_url"):
        return
    msg = Message(sender_id=current_user.id, receiver_id=other_id, content=text or None, file_url=data.get("file_url"))
    db.session.add(msg)
    db.session.commit()
    room = dm_room(current_user.id, other_id)
    payload = {
        "id": msg.id,
        "sender_id": current_user.id,
        "receiver_id": other_id,
        "content": msg.content,
        "file_url": msg.file_url,
        "created_at": msg.created_at.isoformat() + "Z",
    }
    emit("new_message", payload, room=room)
    # Directly to receiver if not in room
    for sid in USER_SIDS.get(other_id, []):
        socketio.emit("new_message", payload, to=sid)


# -----------------------
# Calling and WebRTC signaling
# -----------------------
@socketio.on("call_user")
def on_call_user(data):
    other_id = int(data.get("other_id"))
    call_type = data.get("call_type", "video")
    # Optional logging
    try:
        log = CallLog(caller_id=current_user.id, receiver_id=other_id, call_type=call_type, started_at=datetime.utcnow())
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
    # Notify callee
    payload = {
        "from_id": current_user.id,
        "from_name": current_user.username,
        "call_type": call_type
    }
    # DM room (if both are there)
    emit("incoming_call", payload, room=dm_room(current_user.id, other_id))
    # Directly to callee's sids
    for sid in USER_SIDS.get(other_id, []):
        socketio.emit("incoming_call", payload, to=sid)


@socketio.on("webrtc_join")
def on_webrtc_join(data):
    other_id = int(data.get("other_id"))
    room = call_room(current_user.id, other_id)
    join_room(room)
    emit("webrtc_peer_joined", {"user_id": current_user.id}, room=room, include_self=False)


@socketio.on("webrtc_offer")
def on_webrtc_offer(data):
    other_id = int(data.get("to"))
    offer = data.get("offer")
    call_type = data.get("type", "video")
    # Send via call room (if used)
    room = call_room(current_user.id, other_id)
    emit("webrtc_offer", {"offer": offer, "from": current_user.id, "type": call_type}, room=room, include_self=False)
    # Also directly to callee sids to avoid room dependency
    for sid in USER_SIDS.get(other_id, []):
        socketio.emit("webrtc_offer", {"offer": offer, "from": current_user.id, "type": call_type}, to=sid)


@socketio.on("webrtc_answer")
def on_webrtc_answer(data):
    other_id = int(data.get("to"))
    answer = data.get("answer")
    room = call_room(current_user.id, other_id)
    emit("webrtc_answer", {"answer": answer, "from": current_user.id}, room=room, include_self=False)
    for sid in USER_SIDS.get(other_id, []):
        socketio.emit("webrtc_answer", {"answer": answer, "from": current_user.id}, to=sid)


@socketio.on("webrtc_ice_candidate")
def on_webrtc_ice_candidate(data):
    other_id = int(data.get("to"))
    candidate = data.get("candidate")
    room = call_room(current_user.id, other_id)
    emit("webrtc_ice_candidate", {"candidate": candidate, "from": current_user.id}, room=room, include_self=False)
    for sid in USER_SIDS.get(other_id, []):
        socketio.emit("webrtc_ice_candidate", {"candidate": candidate, "from": current_user.id}, to=sid)


@socketio.on("end_call")
def on_end_call(data):
    other_id = int(data.get("to"))
    # Notify the other side
    emit("end_call", {"from": current_user.id}, room=call_room(current_user.id, other_id), include_self=False)
    for sid in USER_SIDS.get(other_id, []):
        socketio.emit("end_call", {"from": current_user.id}, to=sid)
    # Optional: record end time on the latest log between these users
    try:
        log = (CallLog.query
               .filter(
                   db.or_(
                       db.and_(CallLog.caller_id == current_user.id, CallLog.receiver_id == other_id),
                       db.and_(CallLog.caller_id == other_id, CallLog.receiver_id == current_user.id),
                   )
               )
               .order_by(CallLog.started_at.desc())
               .first())
        if log and not log.ended_at:
            log.ended_at = datetime.utcnow()
            db.session.commit()
    except Exception:
        db.session.rollback()


# -----------------------
# Bootstrap
# -----------------------
@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()


# ✅ Auto-create DB tables on first run
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print("⚠️ Database initialization failed:", e)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
