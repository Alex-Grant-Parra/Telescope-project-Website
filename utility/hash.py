import bcrypt

# Hash the password with salt
def hash_password(password):
    salt = bcrypt.gensalt()  # Generate a salt
    return bcrypt.hashpw(password.encode('utf-8'), salt)  # Hash the password with the salt

# Verify the entered password by comparing it with the stored hash
def check_password(entered_password, stored_hash):
    return bcrypt.checkpw(entered_password.encode('utf-8'), stored_hash)
