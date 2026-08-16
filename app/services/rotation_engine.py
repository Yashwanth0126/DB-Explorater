import secrets
import string
import logging

import psycopg2

from app import models
from app.crypto import decrypt_value

logger = logging.getLogger("rotation")


class RotationError(Exception):
    pass


def generate_secure_password(length: int = 24) -> str:
    """Generates a strong random password safe for use in SQL identifiers/values."""
    # Avoid characters that commonly cause quoting issues in connection strings / shells
    alphabet = string.ascii_letters + string.digits + "!@#%^&*()-_=+"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        # ensure at least one of each class for reasonable strength
        if (any(c.islower() for c in pwd) and any(c.isupper() for c in pwd)
                and any(c.isdigit() for c in pwd)):
            return pwd


def rotate_postgres_password(database: models.TargetDatabase, new_password: str) -> None:
    """
    Connects as the admin/superuser and rotates the target application user's password.
    Raises RotationError on any failure.
    """
    admin_password = decrypt_value(database.admin_password_encrypted)

    conn = None
    try:
        conn = psycopg2.connect(
            host=database.host,
            port=database.port,
            dbname=database.db_name,
            user=database.admin_username,
            password=admin_password,
            connect_timeout=10,
        )
        conn.autocommit = True
        with conn.cursor() as cur:
            # target_username is a trusted, admin-configured value (not raw user input),
            # but we still validate it defensively before interpolating into DDL.
            _validate_identifier(database.target_username)
            # psycopg2 can't parameterize identifiers/ALTER USER syntax; password is
            # passed via %s so it's still safely escaped by the driver.
            cur.execute(
                f'ALTER USER "{database.target_username}" WITH PASSWORD %s',
                (new_password,),
            )
    except Exception as exc:
        logger.error("Rotation failed for database %s: %s", database.name, exc)
        raise RotationError(str(exc)) from exc
    finally:
        if conn is not None:
            conn.close()


def _validate_identifier(identifier: str) -> None:
    """Basic guard against SQL identifier injection for the target_username field."""
    if not identifier or not all(c.isalnum() or c in "_-" for c in identifier):
        raise RotationError(f"Unsafe target_username for ALTER USER: {identifier!r}")


def test_connection(database: models.TargetDatabase, username: str, password: str) -> bool:
    """Verifies that the given credential can actually connect to the target database."""
    try:
        conn = psycopg2.connect(
            host=database.host,
            port=database.port,
            dbname=database.db_name,
            user=username,
            password=password,
            connect_timeout=10,
        )
        conn.close()
        return True
    except Exception as exc:
        logger.error("Connection test failed for database %s user %s: %s",
                     database.name, username, exc)
        return False
