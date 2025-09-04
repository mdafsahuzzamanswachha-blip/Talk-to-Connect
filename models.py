from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import Enum
import enum

db = SQLAlchemy()

class CallTypeEnum(enum.Enum):
    AUDIO = "audio"
    VIDEO = "video"

# -----------------------
# User model
# -----------------------
class User(UserMixin, db.Model):
    """Represents a registered user of the chat app."""
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    username = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    avatar = db.Column(db.String(200), default="/static/images/default.png")
    last_seen = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    sent_messages = db.relationship("Message", backref="sender", foreign_keys="Message.sender_id", lazy="dynamic")
    received_messages = db.relationship("Message", backref="receiver", foreign_keys="Message.receiver_id", lazy="dynamic")
    calls_made = db.relationship("CallLog", backref="caller", foreign_keys="CallLog.caller_id", lazy="dynamic")
    calls_received = db.relationship("CallLog", backref="receiver_user", foreign_keys="CallLog.receiver_id", lazy="dynamic")

    def __repr__(self):
        return f"<User {self.username} ({self.email})>"

# -----------------------
# Message model
# -----------------------
class Message(db.Model):
    """Represents a single chat message between two users."""
    __tablename__ = "message"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=True)           # Optional text message
    file_url = db.Column(db.String(300), nullable=True)   # Optional attachment
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<Message {self.id} from {self.sender_id} to {self.receiver_id}>"

# -----------------------
# CallLog model
# -----------------------
class CallLog(db.Model):
    """Represents an audio or video call between two users."""
    __tablename__ = "call_log"

    id = db.Column(db.Integer, primary_key=True)
    caller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    call_type = db.Column(Enum(CallTypeEnum), nullable=False)  # audio | video
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Call {self.id}: {self.caller_id} -> {self.receiver_id} ({self.call_type.value})>"
