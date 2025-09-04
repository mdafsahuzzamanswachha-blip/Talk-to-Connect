from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, login_required, current_user, login_user, logout_user
from flask_socketio import SocketIO, emit
from models import db, User, Message
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chat.db'
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
socketio = SocketIO(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@socketio.on('send_message')
def handle_send_message(data):
    msg = Message(sender_id=data['sender_id'], content=data['content'], created_at=datetime.utcnow())
    db.session.add(msg)
    db.session.commit()
    emit('receive_message', {
        'sender_id': msg.sender_id,
        'content': msg.content,
        'created_at': msg.created_at.isoformat()
    }, broadcast=True)

@socketio.on('set_online')
def handle_online(data):
    emit('presence', {'user_id': data['user_id'], 'status': 'online'}, broadcast=True)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)
