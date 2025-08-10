from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

db = SQLAlchemy()


class Conversation(db.Model):
    __tablename__ = 'conversations'

    id = db.Column(db.Integer, primary_key=True)
    participant_a = db.Column(db.String(255), nullable=False, index=True)
    participant_b = db.Column(db.String(255), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    messages = db.relationship('Message', backref='conversation', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Conversation {self.id} between {self.participant_a} and {self.participant_b}>"


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False)
    from_address = db.Column(db.String(255), nullable=False, index=True)
    to_address = db.Column(db.String(255), nullable=False, index=True)
    body = db.Column(db.Text, nullable=True)
    message_type = db.Column(db.String(20), nullable=False)  # 'sms', 'mms', 'email'
    attachments = db.Column(JSONB, nullable=True)  # store as JSON array
    provider_message_id = db.Column(db.String(255), nullable=True)  # messaging_provider_id or xillio_id
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<Message {self.id} in Conversation {self.conversation_id}>"