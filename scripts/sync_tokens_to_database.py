#!/usr/bin/env python3
"""
Sync existing telescope tokens from api_tokens.json to the database.
This adds any telescope tokens that exist in the JSON file but not in the database.
"""

import os
import sys
import json

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text

def get_app():
    """Get Flask app"""
    from Server import app
    return app

def sync_tokens():
    """Sync telescope tokens from JSON to database"""
    app = get_app()
    
    with app.app_context():
        from app.db import db
        from models.tables import Telescope
        
        # Load tokens from JSON file
        tokens_file = "security/api_tokens.json"
        if not os.path.exists(tokens_file):
            print(f"❌ Tokens file not found: {tokens_file}")
            return
        
        with open(tokens_file, 'r') as f:
            tokens = json.load(f)
        
        print(f"Found {len(tokens)} tokens in {tokens_file}")
        print()
        
        telescopes_synced = 0
        telescopes_skipped = 0
        
        for token, info in tokens.items():
            client_type = info.get('client_type', 'observer')
            name = info.get('name', 'Unknown')
            
            # Only process telescope tokens
            if client_type != 'telescope':
                print(f"⊘ Skipping '{name}' (type: {client_type})")
                telescopes_skipped += 1
                continue
            
            # Check if telescope already exists in database
            existing = Telescope.get_telescope_by_id(name)
            
            if existing:
                print(f"✓ '{name}' already in database (ID: {existing['id']})")
                telescopes_skipped += 1
            else:
                # Add telescope to database
                result = Telescope.add_telescope(
                    telescope_id=name,
                    telescope_type=client_type,
                    ip_address=None,
                    last_seen=None
                )
                
                if result['status'] == 'success':
                    print(f"✓ Added '{name}' to database (ID: {result.get('id')})")
                    telescopes_synced += 1
                else:
                    print(f"❌ Failed to add '{name}': {result['message']}")
        
        print()
        print("=" * 60)
        print(f"Sync completed:")
        print(f"  - Telescopes added: {telescopes_synced}")
        print(f"  - Telescopes skipped: {telescopes_skipped}")
        print("=" * 60)
        
        if telescopes_synced > 0:
            print()
            print("✅ Telescope tokens are now synchronized with the database!")
            print("   When they connect via WebSocket, last_seen and IP will be updated.")

if __name__ == "__main__":
    print("=" * 60)
    print("Telescope Token Sync Script")
    print("=" * 60)
    print("This will sync telescope tokens from api_tokens.json to the database.")
    print()
    
    sync_tokens()
