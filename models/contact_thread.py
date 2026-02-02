from datetime import datetime
from app.db import db
from utility.encryption import EncryptedString


class ContactMessageEntry(db.Model):
    __tablename__ = 'contact_message_entry'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact_message.id'), nullable=False, index=True)
    author = db.Column(db.String(16), nullable=False)  # 'user' | 'admin'
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    subject = db.Column(EncryptedString(255), nullable=True)
    body = db.Column(EncryptedString(), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='contact_entries')
