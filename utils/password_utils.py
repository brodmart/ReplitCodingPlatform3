import logging
from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)

def hash_password(password: str) -> str:
    """
    Hash a password using Werkzeug's secure hash function.
    """
    try:
        return generate_password_hash(password)
    except Exception as e:
        logger.error(f"Error hashing password: {str(e)}")
        raise

def verify_password(password_hash: str, password: str) -> bool:
    """
    Verify a password against its hash using Werkzeug's secure check.
    """
    try:
        return check_password_hash(password_hash, password)
    except Exception as e:
        logger.error(f"Error verifying password: {str(e)}")
        return False