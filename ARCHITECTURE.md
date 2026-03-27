# System Architecture

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           External Systems                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Phone Network (PSTN)    LiveKit Cloud/Server    LLM Providers              │
│       (SIP)                    (WebRTC)        (Gemini/OpenAI/Groq)        │
└─────────────┬──────────────────────┬──────────────────────┬─────────────────┘
              │                      │                      │
              ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LiveKit Gemini Telephony Backend                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │   FastAPI       │    │   AI Agent      │    │   Database      │        │
│  │   Backend       │    │   Workers       │    │   (SQLite/      │        │
│  │                 │    │                 │    │    PostgreSQL)  │        │
│  │ • REST API      │    │ • Conversation  │    │ • Call Analysis │        │
│  │ • Webhooks      │◄──►│ • STT/TTS       │◄──►│ • Metrics       │        │
│  │ • Token Gen     │    │ • LLM Inference │    │ • Health Data   │        │
│  │ • Call Control  │    │ • VAD           │    │                 │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│          │                      │                      │                   │
│          ▼                      ▼                      ▼                   │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│  │   SIP Trunk     │    │   LiveKit       │    │   Configuration │        │
│  │   (Vobiz)       │    │   Rooms         │    │   & Secrets     │        │
│  │                 │    │                 │    │                 │        │
│  │ • Outbound      │    │ • Real-time     │    │ • Environment   │        │
│  │   Calling       │    │   Audio/Video   │    │   Variables     │        │
│  │ • SIP           │    │ • Participant   │    │ • API Keys      │        │
│  │   Integration   │    │   Management    │    │ • Credentials   │        │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. FastAPI Backend (`main.py`)

**Responsibilities:**
- HTTP API server (REST endpoints)
- LiveKit webhook handler
- Token generation service
- Call initiation and control
- Health monitoring

**Key Endpoints:**
- `GET /` - Service status
- `GET /token` - LiveKit access tokens
- `POST /call/outbound` - Initiate outbound calls
- `POST /webhook/` - LiveKit webhooks
- `GET /call/analysis/*` - Call analysis data

**Dependencies:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `python-dotenv` - Environment management
- `livekit` - LiveKit SDK

### 2. AI Agent Workers (`livekit_agent.py`)

**Responsibilities:**
- Real-time voice conversation handling
- Multi-provider LLM orchestration
- Speech-to-Text processing
- Text-to-Speech synthesis
- Voice activity detection

**Architecture:**
```
┌─────────────────────────────────────────────────────────┐
│                    Agent Session                         │
├─────────────────────────────────────────────────────────┤
│  Audio Input → STT → LLM → TTS → Audio Output           │
│       ↑          ↑     ↑     ↑          ↑               │
│  ┌────┴────┐┌────┴────┐┌────┴────┐┌─────┴─────┐         │
│  │ LiveKit ││ Deepgram││ Gemini  ││ Cartesia  │         │
│  │  Audio  ││ or Google││ or OpenAI││ or Google │         │
│  │  Track  ││ Cloud   ││ or Groq ││ Cloud TTS │         │
│  └─────────┘└─────────┘└─────────┘└───────────┘         │
└─────────────────────────────────────────────────────────┘
```

**Provider Fallback Chain:**
1. Primary LLM (configurable via `PRIMARY_LLM_PROVIDER`)
2. Secondary LLM (if primary fails)
3. STT: Deepgram → Google Cloud Speech
4. TTS: Cartesia → Google Cloud TTS → Kokoro

### 3. Outbound Calling System (`outbound_call.py`)

**Call Flow:**
```
1. API Request → 2. Room Creation → 3. Agent Start → 4. SIP Dial → 5. Connection
   (POST /call)      (outbound_*)     (subprocess)    (Vobiz API)    (LiveKit)
```

**Process Management:**
- Each call spawns a separate agent process
- Process lifecycle managed via `_ACTIVE_AGENT_PROCESSES`
- Graceful shutdown on application exit

### 4. Call Analysis System

**Data Flow:**
```
Conversation → QA Extraction → Scoring → Storage → API
   (LiveKit)    (call_analysis)  (0-100)   (DB)    (REST)
```

**Scoring Algorithm:**
- **Base Score**: 30 points
- **Keyword Overlap**: Up to 40 points (based on matched keywords)
- **Answer Length**: Up to 30 points (based on word count)
- **Total**: Min(100, sum of all components)

**Storage Backends:**
- SQLite (default): `data/call_analysis.db`
- PostgreSQL: Configurable via `CALL_ANALYSIS_POSTGRES_DSN`

### 5. Configuration Management

**Layers:**
1. **Environment Variables** (`.env` file)
2. **Runtime Validation** (`validate_telephony_provider_config()`)
3. **Provider Detection** (credential checks)
4. **Fallback Logic** (provider chain)

## Data Flow

### Inbound Call (Webhook Triggered)
```
1. Phone Call → SIP Trunk → LiveKit Room Created → Webhook → FastAPI
2. FastAPI → Start Agent Process → AI Agent Joins Room
3. Conversation → Real-time Audio/LLM Processing
4. Call Ends → Analysis Stored → Results Available via API
```

### Outbound Call (API Triggered)
```
1. API Request (phone_number) → FastAPI
2. Create Room (outbound_<number>) → Start Agent Process
3. SIP Dial (Vobiz API) → Connect to Room
4. Conversation → Analysis → Storage
```

### Analysis Pipeline
```
1. Conversation Transcript → QA Pair Extraction
2. Each QA Pair → Keyword Extraction → Scoring
3. Aggregate Scores → Overall Match Score
4. Store in Database → Make Available via REST API
```

## Scalability Considerations

### Horizontal Scaling
- **FastAPI**: Stateless, can be load balanced
- **LiveKit**: Supports distributed rooms
- **AI Agents**: Each in separate process, can be distributed
- **Database**: PostgreSQL for multi-instance deployment

### Resource Management
- **Memory**: Each agent process ~200-500MB
- **CPU**: STT/TTS processing intensive
- **Network**: Audio streaming bandwidth
- **Database**: Indexed on `room_name` and `started_at`

### Failure Handling
- **LLM Failures**: Automatic fallback to alternative providers
- **STT/TTS Failures**: Provider chain with timeout
- **Process Crashes**: Agent restart via supervisor
- **Database Unavailable**: Analysis queued in memory

## Security Architecture

### Authentication & Authorization
- **LiveKit**: API key/secret for server-side operations
- **Tokens**: JWT tokens with room-specific grants
- **API**: No authentication (assume internal network)
- **SIP Trunk**: Vobiz credentials

### Data Protection
- **Audio**: Encrypted via WebRTC (DTLS/SRTP)
- **Transcripts**: Stored in database (encrypt at rest recommended)
- **API Keys**: Environment variables only
- **Credentials**: Never logged

### Network Security
- **Internal APIs**: Assume trusted network
- **External APIs**: HTTPS required for production
- **Database**: Firewall rules, connection limits
- **SIP**: TLS for SIP signaling

## Monitoring & Observability

### Key Metrics
- **Call Volume**: Number of active/incoming/outbound calls
- **Latency**: STT → LLM → TTS pipeline timing
- **Success Rate**: Call completion percentage
- **Quality Scores**: Average analysis scores
- **Resource Usage**: CPU, memory, network

### Logging
- **Structured Logs**: JSON format with correlation IDs
- **Log Levels**: DEBUG for development, INFO for production
- **Log Storage**: Centralized logging recommended

### Health Checks
- **API Health**: `GET /call/analysis/health`
- **Database**: Connection and query performance
- **LiveKit**: Server connectivity
- **Providers**: LLM/STT/TTS service availability

## Deployment Topologies

### Single Server (Development)
```
┌─────────────────────────────────────────┐
│           Single Server                  │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ FastAPI │  │ Agents  │  │ SQLite  │ │
│  │ (uvicorn)│  │(processes)│ │ (local) │ │
│  └─────────┘  └─────────┘  └─────────┘ │
└─────────────────────────────────────────┘
```

### Multi-Server (Production)
```
┌─────────┐    ┌─────────┐    ┌─────────┐
│ Load    │    │ LiveKit │    │ Postgres│
│ Balancer│───►│ Server  │───►│ Cluster │
└─────────┘    └─────────┘    └─────────┘
     │              │              │
     ▼              ▼              ▼
┌─────────┐    ┌─────────┐    ┌─────────┐
│ FastAPI │    │ Agent   │    │ Redis   │
│ Servers │    │ Workers │    │ (Queue) │
└─────────┘    └─────────┘    └─────────┘
```

## Future Extensions

### Planned Enhancements
1. **Web Dashboard**: Real-time call monitoring
2. **Custom LLM Prompts**: Per-call instruction customization
3. **Multi-language Support**: Additional STT/TTS languages
4. **Call Recording**: Optional audio recording storage
5. **Analytics**: Advanced conversation analytics
6. **WebRTC Client**: Browser-based agent interface

### Integration Points
1. **CRM Systems**: Contact lookup and update
2. **Calendar**: Appointment scheduling
3. **Payment**: Transaction processing
4. **Notifications**: SMS/email follow-ups
5. **Voice Biometrics**: Speaker identification