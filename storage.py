"""
Storage module for managing encrypted PII mappings.
Handles reading/writing encrypted mapping files.
"""
import json
import os
from typing import Dict
from crypto_util import encrypt_data, decrypt_data


class MappingStorage:
    """Manages encrypted storage of PII mappings."""
    
    def __init__(self, filepath: str, encryption_key: bytes):
        """
        Initialize the mapping storage.
        
        Args:
            filepath: Path to the encrypted mappings file
            encryption_key: Fernet encryption key
        """
        self.filepath = filepath
        self.encryption_key = encryption_key
        
    def save_mappings(self, mappings: Dict[str, str]) -> None:
        """
        Save PII mappings to encrypted file.
        
        Args:
            mappings: Dictionary of placeholder -> original PII value
        """
        # Convert dict to JSON string
        json_data = json.dumps(mappings, indent=2)
        
        # Encrypt the JSON data
        encrypted_data = encrypt_data(json_data, self.encryption_key)
        
        # Write encrypted data to file
        with open(self.filepath, 'wb') as f:
            f.write(encrypted_data)
    
    def load_mappings(self) -> Dict[str, str]:
        """
        Load PII mappings from encrypted file.
        
        Returns:
            Dictionary of placeholder -> original PII value
        """
        if not os.path.exists(self.filepath):
            return {}
        
        try:
            # Read encrypted data from file
            with open(self.filepath, 'rb') as f:
                encrypted_data = f.read()
            
            # Decrypt the data
            json_data = decrypt_data(encrypted_data, self.encryption_key)
            
            # Parse JSON and return
            return json.loads(json_data)
        except Exception as e:
            print(f"Error loading mappings: {e}")
            return {}
    
    def add_mappings(self, new_mappings: Dict[str, str]) -> None:
        """
        Add new mappings to existing ones.
        
        Args:
            new_mappings: New mappings to add
        """
        existing_mappings = self.load_mappings()
        existing_mappings.update(new_mappings)
        self.save_mappings(existing_mappings)
    
    def clear_mappings(self) -> None:
        """Clear all stored mappings."""
        if os.path.exists(self.filepath):
            os.remove(self.filepath)
