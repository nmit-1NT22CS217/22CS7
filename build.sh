#!/usr/bin/env bash
# Build script for Render deployment

set -o errexit  # exit on error

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Download spaCy model (fallback if requirements.txt method fails)

python -m spacy download en_core_web_sm 

# Test imports
python -c "
import spacy
import flask
import groq

# Test spaCy model loading
try:
    nlp = spacy.load('en_core_web_sm')
except Exception as e:
    print('   This might cause issues but deployment will continue...')
"