"""
Backfill and add `created_at` column for `user` table if missing, and populate values.
Run with: python scripts/backfill_user_created_at.py
"""
from Server import app
from app.db import db
from datetime import datetime
import sqlite3

with app.app_context():
    engine = db.engine
    conn = engine.raw_connection()
    cursor = conn.cursor()

    # Check if created_at exists
    cursor.execute("PRAGMA table_info('user')")
    columns = [r[1] for r in cursor.fetchall()]
    if 'created_at' not in columns:
        print('Adding created_at column to user table...')
        try:
            cursor.execute("ALTER TABLE user ADD COLUMN created_at DATETIME")
            conn.commit()
            print('Column added.')
        except Exception as e:
            print('Failed to add column:', e)
            conn.rollback()
    else:
        print('created_at column already present.')

    # Backfill missing created_at values
    from models.user import User, AccountStatusHistory

    users = User.query.all()
    updated = 0
    for u in users:
        if not getattr(u, 'created_at', None):
            # Try to use earliest AccountStatusHistory for this user
            try:
                first_history = AccountStatusHistory.query.filter_by(user_id=u.id).order_by(AccountStatusHistory.changed_at.asc()).first()
                if first_history and first_history.changed_at:
                    u.created_at = first_history.changed_at
                else:
                    u.created_at = datetime.utcnow()
                db.session.add(u)
                updated += 1
            except Exception as e:
                print('Error updating user', u.id, e)
    if updated:
        db.session.commit()
    print(f'Backfilled created_at for {updated} users.')
    conn.close()
