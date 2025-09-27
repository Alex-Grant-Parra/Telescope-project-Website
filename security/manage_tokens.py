#!/usr/bin/env python3
"""
Token Management Utility for Telescope WebSocket Server
Use this script to generate and manage authentication tokens for your clients.
"""

import secrets
import json
import os
from datetime import datetime

TOKENS_FILE = "api_tokens.json"

def load_tokens():
    """Load existing tokens from file"""
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_tokens(tokens):
    """Save tokens to file"""
    with open(TOKENS_FILE, 'w') as f:
        json.dump(tokens, f, indent=2)

def generate_token():
    """Generate a secure token"""
    return secrets.token_urlsafe(32)

def add_token(name, client_type="observer"):
    """Add a new token for a client"""
    tokens = load_tokens()
    token = generate_token()
    
    tokens[token] = {
        "client_type": client_type,
        "name": name,
        "created": datetime.now().isoformat()
    }
    
    save_tokens(tokens)
    return token

def list_tokens():
    """List all existing tokens"""
    tokens = load_tokens()
    if not tokens:
        print("No tokens found.")
        return
    
    print("\nExisting API Tokens:")
    print("-" * 80)
    for token, info in tokens.items():
        print(f"Token: {token}")
        print(f"  Name: {info['name']}")
        print(f"  Type: {info['client_type']}")
        print(f"  Created: {info.get('created', 'Unknown')}")
        print()

def revoke_token(token):
    """Revoke a token"""
    tokens = load_tokens()
    if token in tokens:
        info = tokens.pop(token)
        save_tokens(tokens)
        print(f"Token for '{info['name']}' has been revoked.")
    else:
        print("Token not found.")

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
            
            client_type = input("Enter client type (telescope/observer) [observer]: ").strip().lower()
            if client_type not in ["telescope", "observer"]:
                client_type = "observer"
            
            token = add_token(name, client_type)
            print(f"\nNew token generated for '{name}':")
            print(f"Token: {token}")
            print(f"Type: {client_type}")
            print("\n⚠️  IMPORTANT: Store this token securely! You won't be able to retrieve it again.")
            
        elif choice == "2":
            list_tokens()
            
        elif choice == "3":
            token = input("Enter token to revoke: ").strip()
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