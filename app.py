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
import logging

from models import db, User, Message, CallLog

# -----------------------
# Load environment
# -----------------------
load_dotenv()
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "static/uploads")
ALLOWED_EXTENSIONS = set(ext.strip().lower() for ext in os.getenv("ALLOWED_EXTENSIONS", "pdf,doc,docx,jpg,jpeg,png,txt").split(","))

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -----------------------
# App setup
# -----------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config.update(
    SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret"),
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///chat.db"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    UPLOAD_FOLDER=UPLOAD_FOLDER
)

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

# Socket.IO with logging
socketio = SocketIO(app, cors_allowed_origins=os.getenv("CORS_ORIGINS", "*"))

# -----------------------
# Logging
# -----------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TCChat")

# -----------------------
# Presence / Socket tracking
# -----------------------
ONLINE = {}  # user_id -> connection count
USER_SIDS = defaultdict(set)  # user_id -> set of socket IDs

# -----------------------
# Utility functions
# -----------------------
def dm_room(a_id: int, b_id: int) -> str:
    return f"dm:{min(a_id,b_id)}:{max(a_id,b_id)}"

def call_room(a_id: int, b_id: int) -> str:
    return f"call:{min(a_id,b_id)}:{max(a_id,b_id)}"

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -----------------------
# Auth Routes
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
        user = User(email=email, username=username, password=generate_password_hash(password))
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
# API Endpoints
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
    return jsonify([{
        "id": m.id,
        "sender_id": m.sender_id,
        "receiver_id": m.receiver_id,
        "content": m.content,
        "file_url": m.file_url,
        "created_at": m.created_at.isoformat() + "Z"
    } for m in msgs])

@app.route("/upload", methods=["POST"])
@login_required
def upload():
    other_id = int(request.form.get("receiver_id", "0"))
    file = request.files.get("file")
    if not file or file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file"}), 400
    fname = secure_filename(file.filename)
    ext = fname.rsplit(".", 1)[1].lower()
    new_name = f"{uuid4().hex}.{ext}"
    path = os.path.join(app.config["UPLOAD_FOLDER"], new_name)
    file.save(path)
    file_url = f"/{path.replace(os.path.sep,'/')}"
    msg = Message(sender_id=current_user.id, receiver_id=other_id, file_url=file_url)
    db.session.add(msg)
    db.session.commit()
    socketio.emit("new_message", {
        "id": msg.id,
        "sender_id": msg.sender_id,
        "receiver_id": msg.receiver_id,
        "file_url": msg.file_url,
        "created_at": msg.created_at.isoformat() + "Z"
    }, room=dm_room(current_user.id, other_id))
    return jsonify({"ok": True, "message": "File uploaded successfully."})

# -----------------------
# Socket.IO Events
# -----------------------
@socketio.on("connect")
def on_connect():
    if not current_user.is_authenticated:
        return False
    uid = int(current_user.id)
    ONLINE[uid] = ONLINE.get(uid, 0) + 1
    USER_SIDS[uid].add(request.sid)
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    emit("presence", {"user_id": uid, "status": "online"}, broadcast=True)

@socketio.on("disconnect")
def on_disconnect():
    if not current_user.is_authenticated:
        return
    uid = int(current_user.id)
    USER_SIDS[uid].discard(request.sid)
    if not USER_SIDS[uid]:
        USER_SIDS.pop(uid, None)
    ONLINE[uid] = max(0, ONLINE.get(uid, 1) - 1)
    if ONLINE.get(uid) == 0:
        ONLINE.pop(uid, None)
        emit("presence", {"user_id": uid, "status": "offline"}, broadcast=True)

# -----------------------
# WebRTC / Call Events
# -----------------------
# ... similar clean handling as above, structured for maintainability

# -----------------------
# Before Request
# -----------------------
@app.before_request
def update_last_seen():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

# -----------------------
# Database Initialization
# -----------------------
with app.app_context():
    db.create_all()

# -----------------------
# Run Server
# -----------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=os.getenv("DEBUG", "True") == "True")
