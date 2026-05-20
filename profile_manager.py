import os
import json
from vault import _fernet

_PROFILE_DIR = os.path.join(os.path.expanduser('~'), '.jarvis_profiles')
if not os.path.isdir(_PROFILE_DIR):
    os.makedirs(_PROFILE_DIR, exist_ok=True)

def _profile_path(name: str) -> str:
    safe_name = name.replace(' ', '_')
    return os.path.join(_PROFILE_DIR, f"{safe_name}.enc")

def create_profile(name: str, config: dict) -> None:
    """Create a new profile with given configuration dict and store encrypted."""
    data = json.dumps(config).encode('utf-8')
    token = _fernet.encrypt(data)
    with open(_profile_path(name), 'wb') as f:
        f.write(token)

def load_profile(name: str) -> dict:
    """Load and decrypt a profile configuration."""
    try:
        path = _profile_path(name)
        with open(path, 'rb') as f:
            token = f.read()
        return json.loads(_fernet.decrypt(token).decode('utf-8'))
    except Exception:
        return {}

def delete_profile(name: str) -> None:
    """Delete a stored profile."""
    path = _profile_path(name)
    if os.path.exists(path):
        os.remove(path)

def list_profiles() -> list:
    """List all stored profile names."""
    files = [f for f in os.listdir(_PROFILE_DIR) if f.endswith('.enc')]
    return [os.path.splitext(f)[0].replace('_', ' ') for f in files]
