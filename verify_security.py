import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone
import requests
import sys
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from models import User
from database import Base, engine

# 1. Check Passwords in DB are Hashed
def check_db_hashing():
    print("\n1. Checking Password Hashing in Database...")
    with Session(engine) as session:
        admin = session.query(User).filter_by(email="admin@school.com").first()
        if not admin:
            print("❌ Admin user not found!")
            return False
        
        pwd = admin.password_hash
        print(f"   Saved Password Hash: {pwd[:20]}...")
        if pwd.startswith("$2b$") or pwd.startswith("$2a$"):
            print("✅ Password is using Bcrypt (starts with $2b$)")
            return True
        else:
            print("❌ Password does NOT look like Bcrypt!")
            return False

# 2. Check Secret Key Source
def check_secret_key():
    print("\n2. Checking SECRET_KEY Source...")
    from auth import SECRET_KEY
    
    # Read .env manually
    env_keys = {}
    with open(".env", "r") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                env_keys[k] = v
    
    env_secret = env_keys.get("SECRET_KEY")
    if SECRET_KEY == env_secret:
        print(f"✅ SECRET_KEY is loaded from .env")
        print(f"   Value: {SECRET_KEY[:5]}... (masked)")
        if SECRET_KEY == "change-me":
             print("⚠️  Warning: You are using the default 'change-me' key. Update .env!")
        return True
    else:
        print(f"❌ SECRET_KEY mismatch! Loaded: {SECRET_KEY}, .env: {env_secret}")
        return False

# 3. Check Token Expiration
def check_token_expiry():
    print("\n3. Checking Token Expiration...")
    # Login to get token
    resp = requests.post("http://127.0.0.1:8000/auth/login", 
                         json={"email": "admin@school.com", "password": "admin123"})
    if resp.status_code != 200:
        print("❌ Login failed")
        return False
        
    token = resp.json()["access_token"]
    
    # Decode without verifying to check claims
    claims = jwt.get_unverified_claims(token)
    exp = claims.get("exp")
    
    if not exp:
        print("❌ Token has NO expiration (exp) claim!")
        return False
        
    exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    diff = (exp_dt - now).total_seconds() / 60
    
    print(f"   Token matches exp claim: {exp}")
    print(f"   Expires in: {diff:.1f} minutes")
    
    if 59 <= diff <= 61:
        print("✅ Token expires in ~60 minutes")
        return True
    else:
        print(f"❌ Token expiration is {diff} minutes (Expected ~60)")
        return False

# 4. Check Protected Route Failure
def check_auth_failure():
    print("\n4. Checking Protected Route Security...")
    resp = requests.get("http://127.0.0.1:8000/auth/me")
    print(f"   Request without token -> Status: {resp.status_code}")
    
    if resp.status_code == 401:
        print("✅ Correctly returned 401 Unauthorized")
        return True
    else:
        print(f"❌ Failed! Expected 401, got {resp.status_code}")
        return False

if __name__ == "__main__":
    r1 = check_db_hashing()
    r2 = check_secret_key()
    r3 = check_token_expiry()
    r4 = check_auth_failure()
    
    if all([r1, r2, r3, r4]):
        print("\n🎉 ALL SECURITY CHECKS PASSED!")
    else:
        print("\n⚠️ SOME CHECKS FAILED.")
