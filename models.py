# models.py
from datetime import datetime
import enum

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy import Enum as SAEnum

db = SQLAlchemy()


class CallTypeEnum(enum.Enum):
    AUDIO = "audio"
    VIDEO = "video"


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    username = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(255), nullable=False)
    avatar = db.Column(db.String(255), nullable=True, default="/static/images/default.png")
    last_seen = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    # relationships
    sent_messages = db.relationship(
        "Message",
        backref="sender",
        foreign_keys="Message.sender_id",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    received_messages = db.relationship(
        "Message",
        backref="receiver",
        foreign_keys="Message.receiver_id",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    calls_made = db.relationship(
        "CallLog",
        backref="caller",
        foreign_keys="CallLog.caller_id",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )
    calls_received = db.relationship(
        "CallLog",
        backref="callee",
        foreign_keys="CallLog.receiver_id",
        lazy="dynamic",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User {self.id} {self.username}>"


class Message(db.Model):
    __tablename__ = "message"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    content = db.Column(db.Text, nullable=True)           # text message
    file_url = db.Column(db.String(300), nullable=True)   # optional attachment URL
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def serialize(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "content": self.content,
            "file_url": self.file_url,
            "created_at": self.created_at.isoformat() + "Z",
        }

    def __repr__(self):
        return f"<Message {self.id} {self.sender_id}->{self.receiver_id}>"


class CallLog(db.Model):
    __tablename__ = "call_log"

    id = db.Column(db.Integer, primary_key=True)
    caller_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    call_type = db.Column(SAEnum(CallTypeEnum), nullable=False)
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<CallLog {self.id} {self.caller_id}->{self.receiver_id} {self.call_type.value}>"
