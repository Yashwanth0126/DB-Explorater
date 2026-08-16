from cryptography.fernet import Fernet
from app.config import settings

if not settings.encryption_key:
    raise RuntimeError(
        "ENCRYPTION_KEY is not set. Generate one with:\n"
        "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
        "and put it in your .env file."
    )

_fernet = Fernet(settings.encryption_key.encode())


def encrypt_value(plain_text: str) -> str:
    return _fernet.encrypt(plain_text.encode()).decode()


def decrypt_value(encrypted_text: str) -> str:
    return _fernet.decrypt(encrypted_text.encode()).decode()
