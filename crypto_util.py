"""
Simple encryption utilities using Python's built-in hashlib and base64.
"""
import base64
import hashlib
import secrets


def generate_key():

    return base64.urlsafe_b64encode(secrets.token_bytes(32))


def _derive_key(key: bytes) -> bytes:
    """Derive a 32-byte key from the provided key."""
    if isinstance(key, str):
        key = key.encode()
    return hashlib.sha256(key).digest()


def encrypt_data(data: str, key: bytes) -> bytes:
    """
    Encrypt string data using XOR cipher with derived key.
    
    Args:
        data: String data to encrypt
        key: Encryption key
        
    Returns:
        bytes: Encrypted data (base64 encoded)
    """
    derived_key = _derive_key(key)
    data_bytes = data.encode('utf-8')
    
    # XOR encryption
    encrypted = bytearray()
    for i, byte in enumerate(data_bytes):
        encrypted.append(byte ^ derived_key[i % len(derived_key)])
    
    # Encode to base64 for safe storage
    return base64.b64encode(bytes(encrypted))


def decrypt_data(encrypted_data: bytes, key: bytes) -> str:
    """
    Decrypt data using XOR cipher with derived key.
    
    Args:
        encrypted_data: Encrypted bytes data (base64 encoded)
        key: Encryption key
        
    Returns:
        str: Decrypted string data
    """
    derived_key = _derive_key(key)
    
    # Decode from base64
    encrypted_bytes = base64.b64decode(encrypted_data)
    
    # XOR decryption (same as encryption)
    decrypted = bytearray()
    for i, byte in enumerate(encrypted_bytes):
        decrypted.append(byte ^ derived_key[i % len(derived_key)])
    
    return bytes(decrypted).decode('utf-8')


if __name__ == "__main__":
    key = generate_key()
    ENCRYPTION_KEY={key.decode}