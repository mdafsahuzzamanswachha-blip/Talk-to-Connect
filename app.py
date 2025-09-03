import os
from datetime import datetime
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Local imports
from models import db, User, Message, CallLog

load_dotenv()

# -------------------
# Flask setup
# -------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///chat.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# File Upload Config
UPLOAD_FOLDER = os.path.join(os.getcwd(), os.getenv("UPLOAD_FOLDER", "static/uploads"))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = set(
    (os.getenv("ALLOWED_EXTENSIONS", "pdf,doc,docx,jpg,jpeg,png,txt")).split(",")
)

db.init_app(app)

# Login Manager Setup
login_manager = LoginManager(app)
login_manager.login_view = "login"

# SocketIO Setup
socketio = SocketIO(app, cors_allowed_origins="*")  # In production, set specific domain

# -------------------
# Online Presence Tracking
# -------------------
ONLINE = {}

def dm_room(a_id: int, b_id: int) -> str:
    """Direct message room name between two users"""
    a, b = sorted([int(a_id), int(b_id)])
    return f"dm:{a}:{b}"

def call_room(a_id: int, b_id: int) -> str:
    """Call room name between two users"""
    a, b = sorted([int(a_id), int(b_id)])
    return f"call:{a}:{b}"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------
# Auth Routes
# -------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            try:
                user.last_seen = datetime.utcnow()
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                print(f"[ERROR] Updating last_seen failed: {e}")
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

        try:
            hashed = generate_password_hash(password)
            user = User(email=email, username=username, password=hashed)
            db.session.add(user)
            db.session.commit()
            return redirect(url_for("login"))
        except Exception as e:
            db.session.rollback()
            return render_template("register.html", error=f"Error: {str(e)}")

    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# -------------------
# App Pages
# -------------------
@app.route("/")
@login_required
def index():
    users = User.query.filter(User.id != current_user.id).order_by(User.username.asc()).all()
    online_ids = set(ONLINE.keys())
    return render_template("index.html", users=users, online_ids=online_ids)

@app.route("/call/<int:user_id>/<call_type>")
@login_required
def call_page(user_id, call_type):
    if call_type not in ("audio", "video"):
        abort(404)
    peer = User.query.get_or_404(user_id)
    return render_template("call.html", peer=peer, call_type=call_type)

# -------------------
# API Endpoints
# -------------------
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

    return jsonify([
        {
            "id": m.id,
            "sender_id": m.sender_id,
            "receiver_id": m.receiver_id,
            "content": m.content,
            "file_url": m.file_url,
            "created_at": m.created_at.isoformat() + "Z",
        } for m in msgs
    ])

# -------------------
# File Upload
# -------------------
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
    try:
        msg = Message(sender_id=current_user.id, receiver_id=other_id, file_url=file_url)
        db.session.add(msg)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

    payload = {
        "id": msg.id,
        "sender_id": current_user.id,
        "receiver_id": other_id,
        "content": None,
        "file_url": file_url,
        "created_at": msg.created_at.isoformat() + "Z",
    }
    socketio.emit("new_message", payload, room=dm_room(current_user.id, other_id))
    return jsonify({"ok": True, "message": payload})

# -------------------
# Socket.IO Events
# -------------------
@socketio.on("connect")
def on_connect():
    if not current_user.is_authenticated:
        return False
    uid = int(current_user.id)
    ONLINE[uid] = ONLINE.get(uid, 0) + 1
    User.query.filter_by(id=uid).update({"last_seen": datetime.utcnow()})
    db.session.commit()
    emit("presence", {"user_id": uid, "status": "online"}, broadcast=True)

@socketio.on("disconnect")
def on_disconnect():
    if not current_user.is_authenticated:
        return
    uid = int(current_user.id)
    ONLINE[uid] = max(0, ONLINE.get(uid, 1) - 1)
    if ONLINE[uid] == 0:
        ONLINE.pop(uid, None)
        emit("presence", {"user_id": uid, "status": "offline"}, broadcast=True)

@socketio.on("join_dm")
def on_join_dm(data):
    room = dm_room(current_user.id, int(data.get("other_id")))
    join_room(room)
    emit("joined_dm", {"room": room})

@socketio.on("send_message")
def on_send_message(data):
    other_id = int(data.get("other_id"))
    text = (data.get("content") or "").strip()
    if not text and not data.get("file_url"):
        return
    try:
        msg = Message(sender_id=current_user.id, receiver_id=other_id, content=text or None, file_url=data.get("file_url"))
        db.session.add(msg)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[ERROR] Could not save message: {e}")
        return

    payload = {
        "id": msg.id,
        "sender_id": current_user.id,
        "receiver_id": other_id,
        "content": msg.content,
        "file_url": msg.file_url,
        "created_at": msg.created_at.isoformat() + "Z",
    }
    emit("new_message", payload, room=dm_room(current_user.id, other_id))

# -------------------
# WebRTC Events
# -------------------
@socketio.on("call_user")
def on_call_user(data):
    other_id = int(data.get("other_id"))
    call_type = data.get("call_type", "video")
    emit("incoming_call", {
        "from_id": current_user.id,
        "from_name": current_user.username,
        "call_type": call_type
    }, room=dm_room(current_user.id, other_id))

@socketio.on("webrtc_join")
def on_webrtc_join(data):
    room = call_room(current_user.id, int(data.get("other_id")))
    join_room(room)
    emit("webrtc_peer_joined", {"user_id": current_user.id}, room=room, include_self=False)

@socketio.on("webrtc_offer")
def on_webrtc_offer(data):
    room = call_room(current_user.id, int(data.get("other_id")))
    emit("webrtc_offer", {"sdp": data.get("sdp"), "from": current_user.id}, room=room, include_self=False)

@socketio.on("webrtc_answer")
def on_webrtc_answer(data):
    room = call_room(current_user.id, int(data.get("other_id")))
    emit("webrtc_answer", {"sdp": data.get("sdp"), "from": current_user.id}, room=room, include_self=False)

@socketio.on("webrtc_ice_candidate")
def on_webrtc_ice_candidate(data):
    room = call_room(current_user.id, int(data.get("other_id")))
    emit("webrtc_ice_candidate", {"candidate": data.get("candidate"), "from": current_user.id}, room=room, include_self=False)

# -------------------
# Update last_seen before every request
# -------------------
@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

# -------------------
# App Bootstrap
# -------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    port = int(os.getenv("PORT", "5000"))
    socketio.run(app, host="0.0.0.0", port=port, debug=True)
