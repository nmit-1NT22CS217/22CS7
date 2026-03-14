"""Backwards-compatible shim for crypto utilities used by the OCR service."""

from apps.api.crypto_util import (
    generate_key,
    encrypt_data,
    decrypt_data,
    encrypt_bytes,
    decrypt_bytes,
    dke_encrypt,
    dke_decrypt,
)

__all__ = [
    "generate_key",
    "encrypt_data",
    "decrypt_data",
    "encrypt_bytes",
    "decrypt_bytes",
    "dke_encrypt",
    "dke_decrypt",
]
