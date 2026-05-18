#!/usr/bin/env python3
# Token management utility for Telescope WebSocket Server
# Use this script to generate and manage authentication tokens for clients.

import secrets
import os
import sys

# Add parent directory to path so we can import from the server
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def _with_app_context():
    from Server import app
    return app.app_context()


def load_tokens():
    # Load tokens from DB and return display-safe mapping keyed by token ID
    from security.token_store import list_tokens

    view = {}
    with _with_app_context():
        for rec in list_tokens():
            view[str(rec.id)] = {
                "name": rec.name,
                "client_type": rec.client_type,
                "created": rec.created_at.isoformat() if rec.created_at else "Unknown",
                "token_prefix": rec.token_prefix,
            }
    return view

def generate_token():
    # Generate a secure token
    return secrets.token_urlsafe(32)

def add_token(name, client_type="observer", telescope_type=None):
    # Add a new token for a client
    from security.token_store import create_token_record

    with _with_app_context():
        token, _ = create_token_record(name, client_type)
    
    if client_type in {"telescope", "developer"}:
        try:
            from models.tables import Telescope
            from Server import app
            
            with app.app_context():
                result = Telescope.add_telescope(
                    telescope_id=name,
                    ip_address=None,
                    telescope_type=client_type,
                    last_seen=None
                )
                if result["status"] == "success":
                    print(f"Telescope added to database with ID: {result.get('id')}")
                else:
                    print(f"Warning: Failed to add telescope to database: {result['message']}")
        except Exception as e:
            print(f"Warning: Could not add telescope to database: {str(e)}")
            print("Token was still created successfully.")
    
    return token

def list_tokens():
    # List all existing tokens
    tokens = load_tokens()
    if not tokens:
        print("No tokens found.")
        return
    
    print("\nExisting API Tokens:")
    print("-" * 80)
    for token_id, info in tokens.items():
        print(f"Token ID: {token_id}")
        print(f"  Prefix: {info.get('token_prefix', 'Unknown')}...")
        print(f"  Name: {info['name']}")
        print(f"  Type: {info['client_type']}")
        print(f"  Created: {info.get('created', 'Unknown')}")
        print()

def revoke_token(token):
    # Revoke a token
    from security.token_store import revoke_token_by_id

    with _with_app_context():
        rec = revoke_token_by_id(token)

    if rec:
        print(f"Token for '{rec.name}' has been revoked.")
    else:
        print("Token not found (expected token ID).")

def main():
    print("Telescope WebSocket Token Manager")
    print("================================")
    
    while True:
        print("\nOptions:")
        print("1. Generate new token")
        print("2. List existing tokens")
        print("3. Revoke token")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            name = input("Enter client name: ").strip()
            if not name:
                print("Name cannot be empty.")
                continue
            
            client_type = input("Enter client type (telescope/developer/observer) [observer]: ").strip().lower()
            if client_type not in ["telescope", "developer", "observer"]:
                client_type = "observer"
            
            telescope_type = None
            if client_type in {"telescope", "developer"}:
                telescope_type = input("Enter telescope type/model (optional): ").strip()
                if not telescope_type:
                    telescope_type = None
            
            token = add_token(name, client_type, telescope_type)
            print(f"\nNew token generated for '{name}':")
            print(f"Token: {token}")
            print(f"Type: {client_type}")
            if telescope_type:
                print(f"Telescope Type: {telescope_type}")
            print("\nIMPORTANT: Store this token securely. You will not be able to retrieve it again.")
            
        elif choice == "2":
            list_tokens()
            
        elif choice == "3":
            token = input("Enter token ID to revoke: ").strip()
            if token:
                revoke_token(token)
            else:
                print("Token cannot be empty.")
                
        elif choice == "4":
            break
            
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()