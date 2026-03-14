"""
Cryptographic utilities for reversible token storage.

Uses AES-256-GCM for authenticated encryption (AES-GCM) with random nonces.
This matches the "Cryptographic Tokenization Engine" design and keeps stored
mappings confidential even if the storage file is leaked.
"""

import base64
import secrets
from typing import Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def generate_key() -> bytes:
    """Generate a new 256-bit key suitable for AES-256-GCM.

    Returns:
        bytes: URL-safe base64 encoded key (44 bytes string when decoded)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32))


def _normalize_key(key: Union[str, bytes]) -> bytes:
    """Normalize the provided key into raw 32-byte key material."""
    if isinstance(key, str):
        key = key.encode('utf-8')

    # If the input is base64-encoded, decode it to raw bytes
    try:
        decoded = base64.urlsafe_b64decode(key)
        if len(decoded) in (16, 24, 32):
            return decoded
    except Exception:
        pass

    # Fallback: if key is already 32 bytes, use it directly
    if len(key) == 32:
        return key

    # As a last resort, hash to 32 bytes
    from hashlib import sha256

    return sha256(key).digest()


def encrypt_data(data: str, key: Union[str, bytes]) -> bytes:
    """Encrypt string data using AES-256-GCM.

    Args:
        data: Plaintext string
        key: Base64-encoded or raw key material

    Returns:
        bytes: Base64-encoded nonce+ciphertext (with tag)
    """
    aes_key = _normalize_key(key)
    aesgcm = AESGCM(aes_key)

    # Use a 96-bit (12-byte) nonce for AES-GCM
    nonce = secrets.token_bytes(12)
    ciphertext = aesgcm.encrypt(nonce, data.encode('utf-8'), associated_data=None)

    # Store nonce + ciphertext together
    return base64.urlsafe_b64encode(nonce + ciphertext)


def decrypt_data(encrypted_data: bytes, key: Union[str, bytes]) -> str:
    """Decrypt data encrypted via encrypt_data.

    Args:
        encrypted_data: Base64-encoded nonce+ciphertext
        key: Base64-encoded or raw key material

    Returns:
        str: Decrypted plaintext string
    """
    aes_key = _normalize_key(key)
    aesgcm = AESGCM(aes_key)

    decoded = base64.urlsafe_b64decode(encrypted_data)
    nonce = decoded[:12]
    ciphertext = decoded[12:]

    plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=None)
    return plaintext.decode('utf-8')


def encrypt_bytes(data: bytes, key: Union[str, bytes]) -> str:
    """Encrypt raw bytes and return base64-encoded nonce+ciphertext."""
    aes_key = _normalize_key(key)
    aesgcm = AESGCM(aes_key)
    nonce = secrets.token_bytes(12)
    ciphertext = aesgcm.encrypt(nonce, data, associated_data=None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode('utf-8')


def decrypt_bytes(encrypted_b64: str, key: Union[str, bytes]) -> bytes:
    """Decrypt base64-encoded nonce+ciphertext back to raw bytes."""
    aes_key = _normalize_key(key)
    aesgcm = AESGCM(aes_key)
    decoded = base64.urlsafe_b64decode(encrypted_b64)
    nonce = decoded[:12]
    ciphertext = decoded[12:]
    return aesgcm.decrypt(nonce, ciphertext, associated_data=None)


# -----------------------------------------------------------------------------
# Data Key Encryption (DKE) helpers
# -----------------------------------------------------------------------------

def dke_encrypt(plaintext: bytes, master_key: Union[str, bytes]) -> dict:
    """Encrypt plaintext using a randomly generated data key.

    The data key is encrypted with the given master key.

    Returns:
        dict: {
            "encrypted_payload": <base64 str>,
            "encrypted_data_key": <base64 str>
        }
    """
    # Generate a ephemeral data key for this payload
    data_key = secrets.token_bytes(32)
    encrypted_payload = encrypt_bytes(plaintext, data_key)
    encrypted_data_key = encrypt_bytes(data_key, master_key)
    return {
        'encrypted_payload': encrypted_payload,
        'encrypted_data_key': encrypted_data_key
    }


def dke_decrypt(encrypted_payload: str, encrypted_data_key: str, master_key: Union[str, bytes]) -> bytes:
    """Decrypt a payload encrypted with dke_encrypt."""
    data_key = decrypt_bytes(encrypted_data_key, master_key)
    return decrypt_bytes(encrypted_payload, data_key)


if __name__ == "__main__":
    key = generate_key()
    print(f"Generated key: {key.decode()}")
