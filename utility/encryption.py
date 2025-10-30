import os
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from sqlalchemy.types import TypeDecorator, String, TEXT

# Ensure environment is loaded when running outside Flask app context
load_dotenv()

_fernet: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    key = os.getenv('ENCRYPTION_KEY')
    if not key:
        raise ValueError('ENCRYPTION_KEY environment variable is not set')
    # Accept raw string or bytes-safe base64
    if isinstance(key, str):
        key_bytes = key.encode('utf-8')
    else:
        key_bytes = key
    _fernet = Fernet(key_bytes)
    return _fernet


def encrypt_text(value: Optional[str]) -> Optional[str]:
    """Encrypt a string value with Fernet; returns None if input is None.

    Always returns a utf-8 string.
    """
    if value is None:
        return None
    f = _get_fernet()
    # Normalize to str
    if not isinstance(value, str):
        value = str(value)
    return f.encrypt(value.encode('utf-8')).decode('utf-8')


def decrypt_text(value: Optional[str], *, fallback_plaintext: bool = True) -> Optional[str]:
    """Decrypt a Fernet-encrypted string. If decryption fails and
    fallback_plaintext is True, return the original value.
    """
    if value is None:
        return None
    try:
        f = _get_fernet()
        return f.decrypt(str(value).encode('utf-8')).decode('utf-8')
    except Exception:
        # If it's not valid ciphertext (legacy plaintext in DB), optionally pass through
        if fallback_plaintext:
            return value
        raise


class EncryptedString(TypeDecorator):
    """SQLAlchemy type that transparently encrypts/decrypts string values.

    - On write: plaintext -> ciphertext (Fernet)
    - On read: ciphertext -> plaintext; if not decryptable, returns stored value

    Note: Because Fernet is randomized, DB-level unique indexes on the
    encrypted column won't enforce uniqueness of the plaintext. Handle
    uniqueness in application logic if needed.
    """

    impl = TEXT  # Use TEXT to avoid size issues due to ciphertext expansion

    cache_ok = True

    def __init__(self, length: Optional[int] = None, *args, **kwargs):
        # length is accepted for API compatibility but not used by TEXT
        super().__init__(*args, **kwargs)
        self.length = length

    def process_bind_param(self, value, dialect):
        # Called when sending value to DB
        if value is None:
            return None
        return encrypt_text(value)

    def process_result_value(self, value, dialect):
        # Called when loading value from DB
        if value is None:
            return None
        return decrypt_text(value, fallback_plaintext=True)


# Backward-compatible helpers kept for existing imports
def encrypt_email(email: str) -> str:
    return encrypt_text(email)  # type: ignore[arg-type]


def decrypt_email(encrypted_email: str) -> str:
    return decrypt_text(encrypted_email)  # type: ignore[return-value]
