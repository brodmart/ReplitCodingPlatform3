from utils.backup import DatabaseBackup
import time
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_backup_system():
    logger.info("Starting backup system test")
    backup = DatabaseBackup()
    
    # Create multiple backups
    for i in range(3):
        logger.info(f"\nCreating backup {i+1}")
        success, result = backup.create_backup()
        logger.info(f"Success: {success}")
        logger.info(f"Result: {result}")
        time.sleep(2)  # Small delay between backups
    
    # Get and display backup history
    logger.info("\nChecking backup history:")
    history = backup.get_backup_history()
    logger.info(f"Current Version: {history.get('version', 1)}")
    logger.info(f"Total Backups: {len(history.get('backups', []))}")
    
    logger.info("\nRecent Backups:")
    for b in history.get('backups', [])[-3:]:
        logger.info(f"- {b['file']} (Version {b['version']}) - {b['timestamp']}")

if __name__ == "__main__":
    test_backup_system()
