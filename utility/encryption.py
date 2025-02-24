from cryptography.fernet import Fernet
import os

# Initialize Fernet with encryption key
encryption_key = os.getenv('ENCRYPTION_KEY')
fernet = Fernet(encryption_key)

# Encrypt email
def encrypt_email(email):
    return fernet.encrypt(email.encode()).decode()

# Decrypt email
def decrypt_email(encrypted_email):
    return fernet.decrypt(encrypted_email.encode()).decode()
