"""
One-time script to encrypt existing plaintext data in Data.db for tickets and account fields.

Usage:
    Run from the project root with app context:
        python -m scripts.encrypt_existing_data

This will:
- Ensure encryption key is loaded
- Encrypt ContactMessage.email, message, metadata_json, admin_response
- Encrypt ContactMessageEntry.subject, body
- Encrypt User.email (if somehow plaintext), totp_secret, current_2fa_code
- Encrypt AccountStatusHistory.reason

The script is idempotent: if a value is already encrypted, it will be left as-is.
Always make a backup of instance/Data.db before running.
"""

from __future__ import annotations
import os
from typing import Optional

from Server import app  # initializes env and db
from app.db import db

from models.user import User, AccountStatusHistory
from models.contact import ContactMessage
from models.contact_thread import ContactMessageEntry
from utility.encryption import encrypt_text, decrypt_text


def _encrypt_in_place(model, obj, attr: str) -> bool:
    """Encrypt attribute if it's currently plaintext.
    Returns True if a change was made.
    """
    try:
        val = getattr(obj, attr)
    except Exception:
        return False
    if val is None:
        return False
    # If decrypt_text returns the same value, it may be plaintext; encrypt explicitly
    try:
        # Attempt to see if value is decryptable
        dec = decrypt_text(val, fallback_plaintext=False)  # will raise if not ciphertext
        # If we got here, it's already encrypted; nothing to do
        return False
    except Exception:
        # Not decryptable -> likely plaintext; encrypt now via direct assignment
        try:
            ciphertext = encrypt_text(val)
            # Assign ciphertext directly to column bypassing TypeDecorator encrypt-on-bind.
            # This avoids double encryption if the column uses EncryptedString already.
            column = getattr(type(obj), attr)
            db.session.execute(
                db.text(f"UPDATE {type(obj).__tablename__} SET {attr} = :val WHERE id = :id"),
                {"val": ciphertext, "id": getattr(obj, 'id')}
            )
            return True
        except Exception:
            return False


def main():
    changes = 0
    with app.app_context():
        # Users
        for u in User.query.all():
            # email, totp_secret, current_2fa_code are EncryptedString; ensure cipher in DB
            for field in ("email", "totp_secret", "current_2fa_code"):
                try:
                    if _encrypt_in_place(User, u, field):
                        changes += 1
                except Exception:
                    pass
        # Account status reasons
        for r in AccountStatusHistory.query.all():
            try:
                if _encrypt_in_place(AccountStatusHistory, r, "reason"):
                    changes += 1
            except Exception:
                pass
        # Contact messages
        for m in ContactMessage.query.all():
            for field in ("email", "message", "metadata_json", "admin_response"):
                try:
                    if _encrypt_in_place(ContactMessage, m, field):
                        changes += 1
                except Exception:
                    pass
        # Contact entries
        for e in ContactMessageEntry.query.all():
            for field in ("subject", "body"):
                try:
                    if _encrypt_in_place(ContactMessageEntry, e, field):
                        changes += 1
                except Exception:
                    pass
        db.session.commit()
    print(f"Backfill complete. Columns updated: {changes}")


if __name__ == "__main__":
    main()
