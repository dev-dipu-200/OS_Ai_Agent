# Setup Guide

## Quick Start

### 1. Clone and Prepare
```bash
git clone <repository-url>
cd OS_Ai_Agent
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Start the Server
```bash
python main.py
```

### 5. Test the API
```bash
# In another terminal
curl http://localhost:8000/
```

## Detailed Setup

### Prerequisites

#### 1. Python 3.11+
```bash
python --version
# Should show 3.11 or higher
```

#### 2. LiveKit Server
You need a LiveKit server running. Options:
- **LiveKit Cloud**: Sign up at [livekit.io/cloud](https://livekit.io/cloud)
- **Self-hosted**: Follow [LiveKit deployment guide](https://docs.livekit.io/deploy/)

#### 3. API Keys
Gather the following API keys:
- **LiveKit**: API key and secret from your LiveKit server
- **LLM Provider**: At least one of:
  - Google AI Studio (Gemini) API key
  - OpenAI API key
  - Groq API key
- **Speech-to-Text**: At least one of:
  - Deepgram API key
  - Google Cloud Speech credentials (service account JSON)
- **Text-to-Speech**: At least one of:
  - Cartesia API key and voice ID
  - Google Cloud TTS credentials
- **SIP Trunk** (for outbound calls): Vobiz SIP trunk ID

### Step-by-Step Configuration

#### 1. Environment File
Create `.env` from the template:
```bash
cp .env.example .env
```

Edit `.env` with your preferred editor:
```bash
nano .env
# or
vim .env
# or use any text editor
```

#### 2. LiveKit Configuration
```env
# Required
LIVEKIT_URL=wss://your-livekit-server
LIVEKIT_API_KEY=your_api_key_here
LIVEKIT_API_SECRET=your_api_secret_here

# Optional webhook URL (if using automatic agent spawning)
Webhook_URL=https://your-backend-url/webhook/
```

#### 3. LLM Configuration (Choose at least one)

**Option A: Google Gemini**
```env
GOOGLE_API_KEY=your_gemini_api_key_here
GOOGLE_GEMINI_MODEL=gemini-2.5-flash
PRIMARY_LLM_PROVIDER=google
```

**Option B: OpenAI**
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
PRIMARY_LLM_PROVIDER=openai
```

**Option C: Groq**
```env
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
GROQ_BASE_URL=https://api.groq.com/openai/v1
PRIMARY_LLM_PROVIDER=groq
```

#### 4. Speech-to-Text Configuration (Choose at least one)

**Option A: Deepgram (Recommended)**
```env
DEEPGRAM_API_KEY=your_deepgram_api_key_here
```

**Option B: Google Cloud Speech**
```env
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account.json
```

To get Google Cloud credentials:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a service account with "Cloud Speech-to-Text API" access
3. Download the JSON key file
4. Set the path in `.env`

#### 5. Text-to-Speech Configuration (Choose at least one)

**Option A: Cartesia**
```env
CARTESIA_API_KEY=your_cartesia_api_key_here
CARTESIA_VOICE_ID=your_voice_id_here
```

**Option B: Google Cloud TTS**
```env
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your-service-account.json
GOOGLE_TTS_VOICE=en-US-Neural2-F
GOOGLE_TTS_SPEAKING_RATE=0.8
```

**Option C: Kokoro (Local)**
No additional configuration needed, but ensure `kokoro` Python package is installed.

#### 6. Outbound Calling (Optional)
```env
VOBIZ_SIP_TRUNK_ID=your_sip_trunk_id_here
```

#### 7. Database Configuration
```env
# SQLite (default, recommended for development)
CALL_ANALYSIS_DB_BACKEND=sqlite
CALL_ANALYSIS_SQLITE_PATH=/var/www/Dipu/OS_Ai_Agent/data/call_analysis.db

# OR PostgreSQL (for production)
# CALL_ANALYSIS_DB_BACKEND=postgres
# CALL_ANALYSIS_POSTGRES_DSN=postgresql://user:password@localhost:5432/os_ai_agent
```

#### 8. Server Configuration
```env
HOST=0.0.0.0  # Listen on all interfaces
PORT=8000     # Port to listen on
```

### 3. Database Setup

#### SQLite (Default)
No setup required. The database file will be created automatically at the specified path.

#### PostgreSQL
1. Install PostgreSQL:
   ```bash
   # Ubuntu/Debian
   sudo apt-get install postgresql postgresql-contrib
   
   # macOS
   brew install postgresql
   ```

2. Create database and user:
   ```sql
   CREATE DATABASE os_ai_agent;
   CREATE USER os_ai_user WITH PASSWORD 'secure_password';
   GRANT ALL PRIVILEGES ON DATABASE os_ai_agent TO os_ai_user;
   ```

3. Update `.env` with your connection string.

### 4. Verify Installation

#### Check Python Dependencies
```bash
python -c "import fastapi; import livekit; print('Dependencies OK')"
```

#### Validate Configuration
```bash
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

required = ['LIVEKIT_URL', 'LIVEKIT_API_KEY', 'LIVEKIT_API_SECRET']
missing = [var for var in required if not os.getenv(var)]
if missing:
    print(f'Missing: {missing}')
else:
    print('Basic configuration OK')
"
```

### 5. Start the Services

#### Backend Server
```bash
python main.py
```

Expected output:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

#### Test the API
```bash
# In another terminal
curl http://localhost:8000/
```

Should return HTML with API information.

### 6. Configure LiveKit Webhooks (Optional)

For automatic agent spawning when rooms are created:

1. Go to your LiveKit server dashboard
2. Navigate to Webhooks section
3. Add a new webhook:
   - **URL**: `http://your-server:8000/webhook/` (or HTTPS in production)
   - **Events**: Select `room_started`
   - **Secret**: (Optional) Add for verification

### 7. Test Outbound Calling

1. Ensure `VOBIZ_SIP_TRUNK_ID` is set
2. Make a test call:
   ```bash
   curl -X POST http://localhost:8000/call/outbound \
     -H "Content-Type: application/json" \
     -d '{"phone_number": "+1234567890"}'
   ```
3. Check server logs for call progress

## Development Setup

### 1. Install Development Dependencies
```bash
pip install black flake8 pytest pytest-asyncio
```

### 2. Code Formatting
```bash
# Format code
black .

# Check linting
flake8 .
```

### 3. Running Tests
Create a `test_main.py` file with your test cases, then:
```bash
pytest
```

### 4. Debug Mode
Run server with debug logging:
```bash
LOG_LEVEL=DEBUG python main.py
```

## Production Deployment

### 1. Security Considerations

#### Environment Variables
- Never commit `.env` to version control
- Use secret management (AWS Secrets Manager, HashiCorp Vault, etc.)
- Rotate API keys regularly

#### Network Security
- Use HTTPS (configure reverse proxy with SSL)
- Restrict API access with firewall rules
- Use VPN for internal services

#### Database Security
- Use strong passwords
- Enable SSL for database connections
- Regular backups

### 2. Performance Tuning

#### Database
- Add indexes for frequent queries:
  ```sql
  CREATE INDEX idx_call_analyses_room ON call_analyses(room_name);
  CREATE INDEX idx_call_analyses_created ON call_analyses(created_at);
  ```

#### Python
- Use gunicorn with uvicorn workers for production:
  ```bash
  gunicorn main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
  ```

#### LiveKit
- Configure appropriate room timeouts
- Monitor participant limits

### 3. Monitoring

#### Logging
Configure structured logging:
```python
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
    datefmt='%Y-%m-%dT%H:%M:%SZ'
)
```

#### Health Checks
Implement comprehensive health checks:
- Database connectivity
- LiveKit server status
- External API availability

### 4. Scaling

#### Horizontal Scaling
1. **Load Balancer**: Distribute traffic across multiple backend instances
2. **Database**: Use PostgreSQL with connection pooling
3. **Cache**: Add Redis for token caching
4. **Queue**: Use message queue for call processing

#### Configuration
```env
# Multiple instances
INSTANCE_ID=1
REDIS_URL=redis://localhost:6379/0
```

## Troubleshooting

### Common Issues

#### 1. "ModuleNotFoundError"
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

#### 2. "No LLM provider is configured"
- Check that at least one of `GOOGLE_API_KEY`, `OPENAI_API_KEY`, or `GROQ_API_KEY` is set
- Verify the `.env` file is loaded (check `load_dotenv()`)

#### 3. "LiveKit connection failed"
- Verify `LIVEKIT_URL` is correct (include `wss://` or `https://`)
- Check API key and secret
- Test connectivity: `curl https://your-livekit-server`

#### 4. "Database connection error"
- For SQLite: Check file permissions
- For PostgreSQL: Verify database is running and credentials are correct

#### 5. "Outbound calls failing"
- Verify `VOBIZ_SIP_TRUNK_ID` is set
- Check LiveKit SIP configuration
- Ensure phone number is in E.164 format (+CountryCodeNumber)

### Debug Logging

Enable verbose logging:
```bash
# Set environment variable
export LOG_LEVEL=DEBUG

# Or modify main.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Checking Service Status

```bash
# Check if server is running
curl -f http://localhost:8000/ || echo "Server not running"

# Check database health
curl http://localhost:8000/call/analysis/health

# Check LiveKit connectivity
python -c "
import os
from livekit import api
lk = api.LiveKitAPI(
    url=os.getenv('LIVEKIT_URL'),
    api_key=os.getenv('LIVEKIT_API_KEY'),
    api_secret=os.getenv('LIVEKIT_API_SECRET')
)
print('LiveKit connection OK')
"
```

## Upgrading

### 1. Backup
```bash
# Backup database
cp data/call_analysis.db data/call_analysis.db.backup

# Backup environment
cp .env .env.backup
```

### 2. Update Code
```bash
git pull origin main
```

### 3. Update Dependencies
```bash
pip install -r requirements.txt --upgrade
```

### 4. Migrate Database
Check if any schema changes are needed in `call_analysis_store.py`.

### 5. Restart Services
```bash
# Graceful restart
pkill -f "python main.py"
python main.py
```

## Uninstallation

### 1. Stop Services
```bash
pkill -f "python main.py"
pkill -f "livekit_agent.py"
```

### 2. Remove Files
```bash
# Remove virtual environment
rm -rf venv

# Remove database (optional)
rm -rf data/call_analysis.db

# Remove logs
rm -rf KMS/logs/*

# Keep .env for future reference
```

### 3. Clean Up Dependencies
```bash
pip freeze | xargs pip uninstall -y
```

## Getting Help

### 1. Check Logs
```bash
# Server logs
tail -f nohup.out  # or wherever logs are directed

# Application logs
grep "ERROR\|WARNING" /var/log/your-app.log
```

### 2. Community Resources
- [LiveKit Documentation](https://docs.livekit.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Project Issue Tracker](https://github.com/your-repo/issues)

### 3. Diagnostic Commands
```bash
# System status
python diagnostic.py  # Create this script if needed

# Configuration check
python -c "from outbound_call import validate_telephony_provider_config; validate_telephony_provider_config()"
```

## Next Steps

After successful setup:

1. **Test basic functionality**: Make a test call
2. **Integrate with your application**: Use the API endpoints
3. **Monitor performance**: Set up logging and monitoring
4. **Scale for production**: Follow production deployment guidelines
5. **Customize**: Modify agent behavior, prompts, and analysis logic