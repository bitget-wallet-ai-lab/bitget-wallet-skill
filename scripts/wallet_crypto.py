#!/usr/bin/env python3
"""
AES-256-GCM encrypt/decrypt using password SHA256 as key.
Used for mnemonic and private keys in wallet JSON storage.
"""

import base64
import hashlib
import os
import sys

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    print("Error: cryptography library required", file=sys.stderr)
    print("Run: pip install cryptography", file=sys.stderr)
    sys.exit(1)


def password_to_key(password: str) -> bytes:
    """Convert password to 32-byte AES-256 key (SHA256 hash)."""
    return hashlib.sha256(password.encode("utf-8")).digest()


def encrypt(plaintext: str, password: str) -> str:
    """
    Encrypt plaintext string with AES-256-GCM.
    Returns base64(iv + ciphertext + tag).
    """
    key = password_to_key(password)
    iv = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    return base64.b64encode(iv + ciphertext).decode("ascii")


def decrypt(encrypted_b64: str, password: str) -> str:
    """
    Decrypt base64 string produced by encrypt().
    """
    key = password_to_key(password)
    raw = base64.b64decode(encrypted_b64.encode("ascii"))
    if len(raw) < 12 + 16:
        raise ValueError("Invalid encrypted data")
    iv = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ciphertext, None).decode("utf-8")
