import os
from cryptography.fernet import Fernet

# Local fallback key file — used only if ENCRYPTION_KEY is not set in the
# environment. Without persisting this, a new key was generated on every
# call, silently breaking decrypt() for anything encrypted moments earlier.
_KEY_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".encryption_key")

_fernet_instance = None


def _load_or_create_key() -> bytes:
    env_key = os.getenv("ENCRYPTION_KEY")
    if env_key:
        return env_key.encode() if isinstance(env_key, str) else env_key

    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "rb") as f:
            return f.read().strip()

    # First-time setup: generate once, persist to disk, warn loudly.
    key = Fernet.generate_key()
    with open(_KEY_FILE, "wb") as f:
        f.write(key)
    print(f"[SETUP] No ENCRYPTION_KEY found in environment.")
    print(f"[SETUP] Generated a key and persisted it to {_KEY_FILE} so encryption stays consistent across runs.")
    print(f"[SETUP] For production, copy this into your .env as ENCRYPTION_KEY={key.decode()}")
    return key


def get_fernet() -> Fernet:
    global _fernet_instance
    if _fernet_instance is None:
        _fernet_instance = Fernet(_load_or_create_key())
    return _fernet_instance


def encrypt(data: str) -> str:
    return get_fernet().encrypt(data.encode()).decode()


def decrypt(token: str) -> str:
    return get_fernet().decrypt(token.encode()).decode()
