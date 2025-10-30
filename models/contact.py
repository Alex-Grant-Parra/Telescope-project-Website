from datetime import datetime
import json
import os
from app.db import db


class ContactMessage(db.Model):
    __tablename__ = "contact_message"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    email = db.Column(db.String(255), nullable=False)
    message_type = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(512), nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)  # Store JSON-encoded metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(32), default='new', nullable=False)  # new, in_progress, resolved, closed
    admin_response = db.Column(db.Text, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', backref='contact_messages')
    # Threaded conversation entries for this ticket
    entries = db.relationship('ContactMessageEntry', backref='contact', cascade='all, delete-orphan')

    @property
    def meta(self):
        try:
            return json.loads(self.metadata_json) if self.metadata_json else {}
        except Exception:
            return {}

    @meta.setter
    def meta(self, value):
        try:
            self.metadata_json = json.dumps(value or {})
        except Exception:
            self.metadata_json = None

    @staticmethod
    def uploads_dir(base_dir):
        return os.path.join(base_dir, 'instance', 'uploads', 'contact')
