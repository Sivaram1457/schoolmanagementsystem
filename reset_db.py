"""
reset_db.py — DANGER: Drops all tables and recreates them with the new schema.
Use this when you've modified models.py and need to apply changes in a dev environment.
"""

from database import Base, engine
from models import User, Class  # Import all models to ensure they are registered

import sys

def reset_database():
    print("⚠️  WARNING: This will DROP ALL DATA in 'school_db'.")
    if "--force" in sys.argv:
        print("Force flag detected. Proceeding...")
    else:
        confirm = input("Are you sure? (y/n): ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            return

    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    
    print("Creating all tables (with new schema)...")
    Base.metadata.create_all(bind=engine)
    
    print("✅ Database reset complete.")
    print("Now run: python seed_admin.py")

if __name__ == "__main__":
    reset_database()
