"""
Initialize the memory management system
"""
from utils.memory_manager import MemoryManager
import os

def main():
    memory_manager = MemoryManager()
    
    # Ensure memory_backups directory exists
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(base_dir, 'memory_backups'), exist_ok=True)
    
    # Validate all files
    validation_results = memory_manager.validate_files()
    print("\nFile Validation Results:")
    for file, is_valid in validation_results.items():
        print(f"{file}: {'Valid' if is_valid else 'Invalid'}")
    
    # Update timestamps
    updated_files = memory_manager.update_all_timestamps()
    print("\nUpdated timestamps in:")
    for file in updated_files:
        print(f"- {file}")

if __name__ == "__main__":
    main()
