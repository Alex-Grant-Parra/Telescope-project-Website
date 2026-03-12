#!/usr/bin/env python3
"""
Database migration script to create/update the telescopes table.
Run this script to set up the new telescope tracking schema.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.db import db
from sqlalchemy import text

# We'll create the app context directly without importing Telescope model yet
def get_app():
    """Get Flask app without triggering full initialization"""
    import flask
    from flask_sqlalchemy import SQLAlchemy
    
    # Get the existing app instance
    from Server import app
    return app

def create_telescopes_table():
    """Create the telescopes table with the new schema"""
    app = get_app()
    
    with app.app_context():
        try:
            # Check if table exists
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            
            if 'telescopes' in inspector.get_table_names():
                print("⚠️  Telescopes table already exists.")
                print("\nCurrent columns:")
                cols = inspector.get_columns('telescopes')
                for col in cols:
                    print(f"  - {col['name']}: {col['type']}")
                
                print("\n⚠️  WARNING: This will DROP the existing table and all data!")
                print("New schema will have: id, telescope_id, ip_address, type, last_seen")
                response = input("\nDo you want to drop and recreate it? (yes/no): ").strip().lower()
                if response != 'yes':
                    print("Migration cancelled.")
                    return
                
                # Backup existing data
                try:
                    backup_data = []
                    result = db.session.execute(text("SELECT * FROM telescopes"))
                    for row in result:
                        backup_data.append(dict(row._mapping))
                    print(f"✓ Backed up {len(backup_data)} existing telescope records")
                except Exception as e:
                    print(f"⚠️  Could not backup data: {e}")
                    backup_data = []
                
                # Drop the existing table
                db.session.execute(text("DROP TABLE IF EXISTS telescopes"))
                db.session.commit()
                print("✓ Dropped existing telescopes table")
            else:
                backup_data = []
            
            # Create the table with new schema using raw SQL
            create_sql = """
            CREATE TABLE telescopes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telescope_id VARCHAR(255) NOT NULL UNIQUE,
                ip_address VARCHAR(45),
                type VARCHAR(100),
                last_seen FLOAT
            )
            """
            db.session.execute(text(create_sql))
            
            # Create index on telescope_id
            db.session.execute(text("CREATE INDEX idx_telescope_id ON telescopes(telescope_id)"))
            db.session.commit()
            
            print("✓ Created telescopes table with schema:")
            print("  - id (INTEGER PRIMARY KEY AUTO INCREMENT)")
            print("  - telescope_id (STRING(255), UNIQUE, INDEXED)")
            print("  - ip_address (STRING(45))")
            print("  - type (STRING(100))")
            print("  - last_seen (FLOAT)")
            
            if backup_data:
                print(f"\nAttempting to restore {len(backup_data)} records...")
                restored = 0
                for old_record in backup_data:
                    try:
                        # Map old columns to new columns
                        new_record = {
                            'telescope_id': old_record.get('telescopeId') or old_record.get('telescope_id'),
                            'ip_address': old_record.get('ipAddress') or old_record.get('ip_address'),
                            'type': old_record.get('firmwareVersion') or old_record.get('type') or 'Unknown',
                            'last_seen': old_record.get('lastSeen') or old_record.get('last_seen')
                        }
                        
                        if new_record['telescope_id']:  # Only restore if we have a telescope_id
                            db.session.execute(
                                text("INSERT INTO telescopes (telescope_id, ip_address, type, last_seen) "
                                     "VALUES (:telescope_id, :ip_address, :type, :last_seen)"),
                                new_record
                            )
                            restored += 1
                    except Exception as e:
                        print(f"  ⚠️  Could not restore record: {e}")
                
                db.session.commit()
                print(f"✓ Restored {restored} records to new schema")
            
            print("\n✅ Migration completed successfully!")
            print("\n📋 Next steps:")
            print("   1. Re-generate telescope tokens (they will be added to the DB automatically)")
            print("   2. Update any existing telescope API keys if needed")
            
        except Exception as e:
            print(f"❌ Error during migration: {str(e)}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    print("=" * 60)
    print("Telescope Table Migration Script")
    print("=" * 60)
    print("\nThis will create/update the telescopes table with the new schema.")
    print("The new schema includes: id, telescope_id, ip_address, type, last_seen")
    print()
    
    create_telescopes_table()
