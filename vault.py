import os
import base64
import json
from cryptography.fernet import Fernet
import keyring

VAULT_DIR = os.path.join(os.path.expanduser('~'), '.jarvis_vault')
if not os.path.isdir(VAULT_DIR):
    os.makedirs(VAULT_DIR, exist_ok=True)

def _get_key() -> bytes:
    """Retrieve the encryption key from the OS credential store or generate a new one."""
    stored = keyring.get_password('JARVIS_VAULT', 'encryption_key')
    if stored:
        return base64.urlsafe_b64decode(stored)
    # generate new key
    key = Fernet.generate_key()
    # store as base64 string for keyring compatibility
    keyring.set_password('JARVIS_VAULT', 'encryption_key', base64.urlsafe_b64encode(key).decode())
    return key

_fernet = Fernet(_get_key())

def _secret_path(name: str) -> str:
    safe_name = name.replace(' ', '_')
    return os.path.join(VAULT_DIR, f"{safe_name}.enc")

def store_secret(name: str, data: str) -> None:
    """Encrypt and store a secret under the given name."""
    token = _fernet.encrypt(data.encode('utf-8'))
    with open(_secret_path(name), 'wb') as f:
        f.write(token)

def retrieve_secret(name: str) -> str:
    """Retrieve and decrypt a secret. Raises FileNotFoundError if not present."""
    path = _secret_path(name)
    with open(path, 'rb') as f:
        token = f.read()
    return _fernet.decrypt(token).decode('utf-8')

def list_secrets() -> list:
    """Return a list of stored secret names (without extension)."""
    files = [f for f in os.listdir(VAULT_DIR) if f.endswith('.enc')]
    return [os.path.splitext(f)[0].replace('_', ' ') for f in files]

def delete_secret(name: str) -> None:
    """Delete a stored secret. Raises FileNotFoundError if not present."""
    path = _secret_path(name)
    os.remove(path)
