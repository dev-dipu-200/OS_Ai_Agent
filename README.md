# LiveKit Gemini Telephony Backend

A sophisticated AI-powered telephony system built with LiveKit, FastAPI, and multiple LLM providers for intelligent voice conversations, outbound calling, and call analysis.

## Overview

This project provides a complete backend for AI-powered telephony applications, featuring:

- **AI Voice Assistant**: Real-time conversational AI using Gemini, OpenAI, or Groq LLMs
- **Outbound Calling**: Initiate phone calls via SIP trunking (Vobiz integration)
- **Call Analysis**: Automatic scoring and analysis of conversation quality
- **Multi-provider Support**: Flexible LLM, STT, and TTS providers
- **Webhook Integration**: LiveKit webhook handling for automatic agent spawning

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Phone Network │◄────┤   LiveKit SIP   │◄────┤   Outbound API  │
│   (PSTN/SIP)    │     │     (Vobiz)     │     │  (FastAPI)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Participant   │────►│   LiveKit Room  │◄────┤   AI Agent      │
│   (Human)       │     │                 │     │  (Worker)       │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                            │
│  • Webhook handling    • Token generation    • Call analysis    │
│  • Health endpoints    • Configuration       • Database         │
└─────────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. **FastAPI Backend** (`main.py`)
- REST API for outbound call initiation
- LiveKit token generation
- Webhook endpoint for automatic agent spawning
- Call analysis endpoints

### 2. **LiveKit AI Agent** (`livekit_agent.py`)
- Real-time voice conversation handler
- Multi-LLM provider support (Google Gemini, OpenAI, Groq)
- Speech-to-Text (Deepgram, Google Cloud Speech)
- Text-to-Speech (Cartesia, Google Cloud TTS, Kokoro)
- Voice Activity Detection (Silero VAD)

### 3. **Outbound Calling** (`outbound_call.py`)
- SIP trunk integration via Vobiz
- Room creation and agent process management
- Phone number validation and dialing

### 4. **Call Analysis** (`call_analysis.py`, `call_analysis_store.py`)
- Conversation scoring based on keyword matching
- SQLite/PostgreSQL storage backend
- QA pair extraction and analysis
- Health monitoring endpoints

### 5. **TTS Services** (`kokoro_tts.py`)
- Kokoro TTS integration for high-quality voice synthesis
- Pipeline-based audio generation

## Installation

### Prerequisites
- Python 3.11+
- LiveKit server (self-hosted or cloud)
- Vobiz SIP trunk account (for outbound calls)
- API keys for LLM/STT/TTS providers

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd OS_Ai_Agent
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Set up database** (optional)
   ```bash
   # SQLite is used by default
   # For PostgreSQL, update CALL_ANALYSIS_DB_BACKEND in .env
   ```

## Configuration

### Required Environment Variables

#### LiveKit Configuration
```env
LIVEKIT_URL=wss://your-livekit-server
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
```

#### LLM Providers (at least one required)
```env
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_GEMINI_MODEL=gemini-2.5-flash

OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini

GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant
PRIMARY_LLM_PROVIDER=google  # google, openai, or groq
```

#### Speech-to-Text (at least one required)
```env
DEEPGRAM_API_KEY=your_deepgram_key
# OR Google Cloud Speech
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

#### Text-to-Speech (at least one required)
```env
# Cartesia
CARTESIA_API_KEY=your_cartesia_key
CARTESIA_VOICE_ID=your_voice_id

# OR Google Cloud TTS
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
GOOGLE_TTS_VOICE=en-US-Neural2-F
GOOGLE_TTS_SPEAKING_RATE=0.8
```

#### Outbound Calling
```env
VOBIZ_SIP_TRUNK_ID=your_sip_trunk_id
```

#### Database
```env
CALL_ANALYSIS_DB_BACKEND=sqlite  # or postgres
CALL_ANALYSIS_SQLITE_PATH=/var/www/Dipu/OS_Ai_Agent/data/call_analysis.db
CALL_ANALYSIS_POSTGRES_DSN=postgresql://user:password@localhost:5432/os_ai_agent
```

#### Server
```env
HOST=0.0.0.0
PORT=8000
```

## Usage

### Starting the Backend

```bash
python main.py
```

The server will start on `http://localhost:8000` (or configured host/port).

### API Endpoints

#### 1. **Home Page** `GET /`
- Basic information about available endpoints

#### 2. **Token Generation** `GET /token`
- Generate LiveKit access tokens
- Parameters: `room` (default: "default-room"), `identity` (default: "ai-agent")

#### 3. **Outbound Call** `POST /call/outbound`
- Initiate an outbound call to a phone number
- Request body: `{"phone_number": "+1234567890"}`
- Response: `{"status": "success", "message": "Call initiated to +1234567890"}`

#### 4. **Call Analysis**
- `GET /call/analysis/latest` - Get latest call analysis
- `GET /call/analysis/latest/summary` - Get summarized latest analysis
- `GET /call/analysis/{analysis_id}` - Get analysis by ID
- `GET /call/analysis/health` - Database health check

#### 5. **Webhook** `POST /webhook/`
- LiveKit webhook endpoint for automatic agent spawning
- Handles `room_started` events

### Running the AI Agent

The agent can be started manually:

```bash
python livekit_agent.py connect --room <room_name>
```

Or automatically via webhooks when a room is created.

### Making an Outbound Call

1. Ensure all required environment variables are set
2. Start the backend server
3. Send a POST request to `/call/outbound`:
   ```bash
   curl -X POST http://localhost:8000/call/outbound \
     -H "Content-Type: application/json" \
     -d '{"phone_number": "+1234567890"}'
   ```
4. The system will:
   - Create a LiveKit room
   - Start an AI agent in that room
   - Dial the phone number via Vobiz SIP trunk
   - Connect the call to the AI agent

## Call Analysis

The system automatically analyzes conversations by:

1. **Extracting QA pairs** from the conversation transcript
2. **Scoring answers** based on:
   - Keyword overlap with questions (40%)
   - Answer length (30%)
   - Base score (30%)
3. **Storing results** in the configured database
4. **Providing insights** through the analysis API

### Analysis Metrics
- `overall_match_score`: Overall conversation quality (0-100)
- `total_pairs`: Total number of question-answer pairs
- `answered_pairs`: Number of answered questions
- `unanswered_pairs`: Number of unanswered questions
- `duration_seconds`: Call duration
- `close_reason`: How the call ended

## Development

### Project Structure
```
.
├── main.py                 # FastAPI backend
├── livekit_agent.py        # AI agent implementation
├── outbound_call.py        # Outbound calling logic
├── call_analysis.py        # Call analysis scoring
├── call_analysis_store.py  # Database operations
├── kokoro_tts.py          # Kokoro TTS service
├── requirements.txt        # Python dependencies
├── .env.example           # Environment template
├── data/                  # SQLite database directory
└── KMS/                   # Key management/logs
```

### Adding New LLM Providers

1. Add provider detection in `livekit_agent.py::_build_llm()`
2. Import the provider from `livekit.plugins`
3. Add environment variable for API key
4. Update validation in `outbound_call.py::validate_telephony_provider_config()`

### Adding New TTS/STT Providers

1. Import the provider from `livekit.plugins`
2. Update provider selection logic in `livekit_agent.py`
3. Add credential validation functions

## Troubleshooting

### Common Issues

1. **"No LLM provider is configured"**
   - Ensure at least one of `GOOGLE_API_KEY`, `OPENAI_API_KEY`, or `GROQ_API_KEY` is set

2. **"Telephony STT is not configured"**
   - Set `DEEPGRAM_API_KEY` or configure Google Cloud credentials

3. **"Telephony TTS is not configured"**
   - Set `CARTESIA_API_KEY` with `CARTESIA_VOICE_ID` or configure Google Cloud TTS

4. **Outbound calls failing**
   - Verify `VOBIZ_SIP_TRUNK_ID` is set correctly
   - Check LiveKit server connectivity
   - Ensure SIP trunk is properly configured in Vobiz

5. **Database errors**
   - Check database connection string
   - Ensure write permissions for SQLite file
   - Verify PostgreSQL is running if using PostgreSQL backend

### Logging

Logs are configured at INFO level by default. To enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Considerations

- **Voice Latency**: Use geographically close LiveKit servers
- **LLM Selection**: Gemini 2.5 Flash offers good balance of speed and quality
- **Database**: PostgreSQL recommended for production with high call volume
- **Resource Usage**: Each agent runs in a separate process; monitor system resources

## Security

- **API Keys**: Store securely in environment variables, not in code
- **LiveKit Tokens**: Use short-lived tokens with appropriate grants
- **Database**: Use strong passwords and network isolation
- **SIP Trunk**: Restrict SIP trunk access to trusted IPs

## Deployment

### Docker (Example)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

### Production Considerations
1. Use process manager (systemd, supervisor, or container orchestration)
2. Implement HTTPS with reverse proxy (nginx, Caddy)
3. Set up monitoring and alerting
4. Regular database backups
5. Rate limiting for API endpoints

## License

[Specify license]

## Support

For issues and feature requests, please use the project's issue tracker.

## Acknowledgments

- [LiveKit](https://livekit.io/) for real-time communication infrastructure
- [Google Gemini](https://ai.google.dev/) for LLM capabilities
- [Vobiz](https://vobiz.com/) for SIP trunking services
- All other open-source libraries used in this project