from datetime import datetime
from sqlalchemy import inspect, text
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
    file_path = db.Column(db.String(512), nullable=True)
    original_filename = db.Column(EncryptedString(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='contact_entries')


def ensure_contact_entry_attachment_columns():
    # Ensure attachment related columns exist on contact_message_entry
    engine = db.engine
    inspector = inspect(engine)

    if 'contact_message_entry' not in inspector.get_table_names():
        return

    existing_cols = {c['name'] for c in inspector.get_columns('contact_message_entry')}
    required_cols = {
        'file_path': 'VARCHAR(512)',
        'original_filename': 'TEXT',
    }

    with engine.begin() as conn:
        for col_name, col_type in required_cols.items():
            if col_name not in existing_cols:
                conn.execute(text(f"ALTER TABLE contact_message_entry ADD COLUMN {col_name} {col_type}"))
