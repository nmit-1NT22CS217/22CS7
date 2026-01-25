"""
Production configuration for PII Anonymizer Flask app.
"""
import os
from crypto_util import generate_key

class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY') or generate_key().decode()
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY') or generate_key().decode()
    GROQ_API_KEY = os.getenv('GROQ_API_KEY')
    GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')
    MAPPINGS_FILE = os.getenv('MAPPINGS_FILE', 'mappings.enc')
    ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*')
    
    # Flask settings
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = True
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False
    
class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False
    
    # Production security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

class TestingConfig(Config):
    """Testing configuration."""
    DEBUG = True
    TESTING = True
    WTF_CSRF_ENABLED = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}