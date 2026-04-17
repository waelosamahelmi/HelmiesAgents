from __future__ import annotations

from base64 import urlsafe_b64encode
from hashlib import sha256
from cryptography.fernet import Fernet


class SecretsVault:
    def __init__(self, key_material: str) -> None:
        key = urlsafe_b64encode(sha256(key_material.encode()).digest())
        self.fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self.fernet.decrypt(ciphertext.encode()).decode()
