import logging
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)
ph = PasswordHasher()

def hash_password(password: str) -> str:
    """
    Hash a password using Argon2.
    """
    try:
        return ph.hash(password)
    except Exception as e:
        logger.error(f"Error hashing password with Argon2: {str(e)}")
        # Fallback to Werkzeug's hashing if Argon2 fails
        return generate_password_hash(password)

def verify_password(password_hash: str, password: str) -> bool:
    """
    Verify a password against its hash, supporting both Argon2 and Werkzeug hashes.
    """
    try:
        # Try Argon2 verification first
        if password_hash.startswith("$argon2"):
            return ph.verify(password_hash, password)
        # Fall back to Werkzeug verification for legacy hashes
        return check_password_hash(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception as e:
        logger.error(f"Error verifying password: {str(e)}")
        return False

def needs_rehash(password_hash: str) -> bool:
    """
    Check if a password hash needs to be upgraded to Argon2.
    """
    return not password_hash.startswith("$argon2")
