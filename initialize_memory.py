"""
Enhanced initialization script for the memory management system
"""
from utils.memory_manager import MemoryManager
import os
import logging
from datetime import datetime

def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)

    try:
        logger.info("Initializing memory management system...")
        memory_manager = MemoryManager()

        # Ensure memory_backups directory exists
        base_dir = os.path.dirname(os.path.abspath(__file__))
        os.makedirs(os.path.join(base_dir, 'memory_backups'), exist_ok=True)

        # Validate all files
        logger.info("Validating memory files...")
        validation_results = memory_manager.validate_files()
        print("\nFile Validation Results:")
        for file, is_valid in validation_results.items():
            status = 'Valid' if is_valid else 'Invalid'
            print(f"{file}: {status}")
            if not is_valid:
                logger.warning(f"Validation failed for {file}")

        # Update timestamps
        logger.info("Updating timestamps...")
        updated_files = memory_manager.update_all_timestamps()
        print("\nUpdated timestamps in:")
        for file in updated_files:
            print(f"- {file}")

        # Log initialization
        logger.info("Memory system initialization completed successfully")
        print(f"\nInitialization completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        logger.error(f"Initialization failed: {str(e)}")
        print("\nError: Memory system initialization failed. Check logs for details.")
        raise

if __name__ == "__main__":
    main()