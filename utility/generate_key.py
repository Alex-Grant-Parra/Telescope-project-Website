# Used to generate cryptography keys, creates as the command to make a environment variable

from cryptography.fernet import Fernet

def generate_key():
    key = Fernet.generate_key()
    print(f'''export ENCRYPTION_KEY="{key.decode()}"''')

if __name__ == "__main__":
    generate_key()
