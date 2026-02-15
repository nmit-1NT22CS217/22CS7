# 🚀 Production Deployment Guide for Render

## Overview
This guide will help you deploy the enhanced PII Anonymizer to Render with all the latest improvements including LLM-friendly semantic labels and context-aware detection.

## 📋 Prerequisites
1. Render account (free tier is sufficient for testing)
2. GitHub repository with your code
3. Groq API key (optional - app works without it)

## 🔧 Environment Variables Setup

### Required Environment Variables
Set these in your Render service environment:

```bash
# Security (REQUIRED)
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-encryption-key-here

# LLM Configuration (OPTIONAL)
GROQ_API_KEY=your-groq-api-key-here
GROQ_MODEL=llama-3.3-70b-versatile

# Flask Configuration
FLASK_DEBUG=False
PORT=10000

# CORS Configuration (adjust for your domain)
ALLOWED_ORIGINS=https://your-domain.com,https://your-frontend.com
```

### 🔑 Generating Keys
To generate the required keys, run locally:
```bash
python crypto_util.py
```
Copy the generated keys to your Render environment variables.

## 📁 File Structure
Ensure these files are in your repository:
```
├── app.py                 # Main Flask application
├── anonymizer.py          # Enhanced PII anonymizer with semantic labels
├── config.py             # Production configuration
├── requirements.txt      # Python dependencies
├── runtime.txt          # Python version
├── Procfile             # Render process configuration
├── build.sh             # Build script
└── templates/
    └── index.html       # Web interface
```

## 🚀 Deployment Steps

### 1. Connect Repository
1. Log into Render dashboard
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Select the branch (usually `main`)

### 2. Configure Service
```yaml
Name: pii-anonymizer-prod
Environment: Python
Build Command: ./build.sh
Start Command: gunicorn -w 4 -b 0.0.0.0:$PORT app:app
```

### 3. Set Environment Variables
In Render dashboard → Environment:
- Add all the environment variables listed above
- **Important**: Set `FLASK_DEBUG=False` for production

### 4. Deploy
- Click "Create Web Service"
- Wait for build and deployment (takes 5-10 minutes)
- Monitor logs for any issues

## 🧪 Testing Deployment

### Health Check
Visit: `https://your-app.onrender.com/api/health`

Expected response:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "anonymizer_healthy": true,
  "llm_mode": "api" or "mock",
  "environment": {
    "python_version": "3.12.7",
    "has_groq_api_key": true,
    "debug_mode": false
  }
}
```

### Startup Check
Visit: `https://your-app.onrender.com/api/startup-check`

This will show detailed status of all components.

### Test Anonymization
```bash
curl -X POST https://your-app.onrender.com/api/anonymize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Account Number: 9876543210\nPhone Number: +1-234-567-8901",
    "action": "anonymize"
  }'
```

Expected response with semantic labels:
```json
{
  "anonymized_text": "Account Number: account_number_1\nPhone Number: mobNo_1",
  "entity_mappings": {
    "account_number_1": "9876543210",
    "mobNo_1": "+1-234-567-8901"
  },
  "mappings_count": 2
}
```

## 🔍 Features Available in Production

### ✅ Enhanced PII Detection
- **Multi-token entities**: Detects names like "Mary Jane Watson-Smith"
- **Context-aware classification**: Distinguishes between account numbers and phone numbers based on context
- **Field label protection**: Won't misclassify "Phone Number" as a person name

### ✅ LLM-Friendly Semantic Labels
- `name_1`, `name_2` instead of `PII_1`, `PII_2`
- `mobNo_1`, `mobNo_2` for phone numbers
- `account_number_1`, `employee_id_1`, etc.
- Much more readable for LLM processing

### ✅ Production Features
- **Secure storage**: Encrypted mapping storage
- **CORS support**: Configurable cross-origin requests
- **Error handling**: Comprehensive error responses
- **Health monitoring**: Multiple health check endpoints
- **Logging**: Detailed operation logs

## 🛠️ Troubleshooting

### Common Issues

1. **spaCy Model Not Found**
   - Check build logs for spaCy download issues
   - Ensure `en-core-web-sm` is properly downloaded
   - The `build.sh` script handles this automatically

2. **Environment Variable Issues**
   - Verify all required environment variables are set
   - Check the `/api/startup-check` endpoint for diagnostics
   - Ensure `SECRET_KEY` and `ENCRYPTION_KEY` are set

3. **Memory Issues**
   - Consider upgrading to a larger Render plan if needed
   - spaCy models require ~500MB RAM minimum

4. **CORS Errors**
   - Set `ALLOWED_ORIGINS` environment variable properly
   - For development, you can use `*` but specify domains in production

### Monitoring
- Use Render's built-in logs and metrics
- Monitor the `/api/health` endpoint
- Set up uptime monitoring (like UptimeRobot) for the health endpoint

## 🔄 Updates and Maintenance

### Deploying Updates
1. Push changes to your connected branch
2. Render automatically rebuilds and deploys
3. Monitor deployment logs for any issues
4. Test the health endpoints after deployment

### Environment Management
- Rotate keys periodically by updating environment variables
- Monitor usage if using Groq API (rate limits apply)
- Backup mapping files if storing important data

## 🎯 Production-Ready Features

Your deployed PII Anonymizer now includes:

- ✅ **Enhanced entity detection** for complex multi-token entities
- ✅ **Semantic labeling system** (name_1, mobNo_1, etc.) instead of generic PII_X
- ✅ **Context-aware classification** preventing field label misdetection
- ✅ **Production security** with encrypted storage and secure configurations
- ✅ **Comprehensive API** with error handling and validation
- ✅ **Health monitoring** endpoints for production monitoring
- ✅ **LLM integration** with optional Groq API support

## 📞 Support

If you encounter issues:
1. Check the health endpoints first
2. Review Render deployment logs
3. Verify environment variables are correctly set
4. Test locally with the same configuration

Your PII Anonymizer is now production-ready with all the enhanced features! 🚀