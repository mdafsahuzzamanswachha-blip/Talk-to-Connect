import os
from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Message

# ------------------ App Config ------------------ #
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "supersecret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///chat.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
socketio = SocketIO(app, cors_allowed_origins="*")
login_manager = LoginManager(app)
login_manager.login_view = "login"


# ------------------ Auth ------------------ #
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"]
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        if User.query.filter_by(email=email).first():
            flash("Email already exists")
            return redirect(url_for("register"))
        user = User(email=email, username=username, password=password)
        db.session.add(user)
        db.session.commit()
        flash("Account created! Please log in.")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("index"))
        flash("Invalid credentials")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ------------------ Routes ------------------ #
@app.route("/")
@login_required
def index():
    return render_template("index.html", username=current_user.username)


@app.route("/call")
@login_required
def call():
    return render_template("call.html", username=current_user.username)


# ------------------ Chat Socket ------------------ #
@socketio.on("message")
def handle_message(msg):
    if current_user.is_authenticated:
        new_msg = Message(sender_id=current_user.id, receiver_id=0, content=msg)
        db.session.add(new_msg)
        db.session.commit()
        send(f"{current_user.username}: {msg}", broadcast=True)


# ------------------ Run ------------------ #
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    socketio.run(app, host="0.0.0.0", port=5000)
