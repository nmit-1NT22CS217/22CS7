"""
Setup script - generates encryption key and checks environment
"""
import os
import secrets
import base64

# Generate a Fernet-compatible key
key = base64.urlsafe_b64encode(secrets.token_bytes(32))
print(key.decode())

# Create .env file
env_content = f"""# Encryption key (REQUIRED)
ENCRYPTION_KEY={key.decode()}


# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=True
"""

with open('.env', 'w') as f:
    f.write(env_content)

print("\n✅ Created .env file with encryption key")

# Check installed packages
print("\n📦 Checking installed packages...")
try:
    import flask
    print("✅ Flask is installed")
except ImportError:
    print("❌ Flask is NOT installed - run: pip install Flask==2.3.3")

try:
    import requests
    print("✅ requests is installed")
except ImportError:
    print("❌ requests is NOT installed - run: pip install requests==2.31.0")

try:
    from dotenv import load_dotenv
    print("✅ python-dotenv is installed")
except ImportError:
    print("❌ python-dotenv is NOT installed - run: pip install python-dotenv==1.0.0")

print("\n📦 Checking encryption...")
try:
    # Test our built-in encryption
    from apps.api.crypto_util import encrypt_data, decrypt_data, generate_key
    test_key = generate_key()
    test_data = "test"
    encrypted = encrypt_data(test_data, test_key)
    decrypted = decrypt_data(encrypted, test_key)
    if test_data == decrypted:
        print("✅ Encryption utilities are working")
    else:
        print("⚠️  Encryption test failed")
except Exception as e:
    print(f"❌ Encryption utilities error: {e}")

try:
    import spacy
    print("✅ spaCy is installed")
    try:
        nlp = spacy.load("en_core_web_sm")
        print("✅ spaCy model 'en_core_web_sm' is installed")
    except OSError:
        print("⚠️  spaCy is installed but model 'en_core_web_sm' is missing")
        print("   Run: python -m spacy download en_core_web_sm")
except ImportError:
    print("❌ spaCy is NOT installed")
    print("   Option 1: pip install spacy (may fail on MSYS2)")
    print("   Option 2: Use app_simple.py without spaCy")

