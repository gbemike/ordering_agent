import time
import hashlib

def generate_user_id(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()[:16]

def generate_session_id(name: str) -> str:
    timestamp = str(int(time.time()))
    base = f"{name}-{timestamp}"
    return hashlib.sha256(base.encode()).hexdigest()[:16]