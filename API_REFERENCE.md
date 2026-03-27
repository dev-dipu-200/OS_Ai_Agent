# API Reference

## Base URL
All endpoints are relative to the server base URL (default: `http://localhost:8000`).

## Authentication
Currently, the API does not implement authentication (assumes internal network access). For production deployments, implement appropriate authentication middleware.

## Endpoints

### 1. Home Page
**GET /**  
Returns a simple HTML page with API information.

**Response:**
```html
<h1>LiveKit Gemini Telephony Backend</h1>
<p>Outbound call endpoint: <code>POST /call/outbound</code></p>
<p>Legacy alias: <code>POST /call</code></p>
<p>Token endpoint: <code>GET /token</code></p>
```

### 2. Token Generation
**GET /token**  
Generates a LiveKit access token for joining rooms.

**Query Parameters:**
- `room` (string, optional): Room name (default: "default-room")
- `identity` (string, optional): Participant identity (default: "ai-agent")

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Example:**
```bash
curl "http://localhost:8000/token?room=test-room&identity=agent-1"
```

### 3. Outbound Call
**POST /call/outbound**  
Initiates an outbound call to a phone number.

**Request Body:**
```json
{
  "phone_number": "+1234567890"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Call initiated to +1234567890"
}
```

**Response (Error):**
```json
{
  "detail": "VOBIZ_SIP_TRUNK_ID is not set in .env"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/call/outbound \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+1234567890"}'
```

### 4. Call Analysis Endpoints

#### 4.1 Get Latest Analysis
**GET /call/analysis/latest**  
Retrieves the most recent call analysis with full details.

**Response:**
```json
{
  "_analysis_id": 42,
  "_backend": "sqlite",
  "room_name": "outbound_1234567890",
  "participant_identity": "sip:1234567890",
  "participant_kind": "sip_participant",
  "started_at": 1743049200.123,
  "ended_at": 1743049260.456,
  "duration_seconds": 60.333,
  "close_reason": "participant_left",
  "overall_match_score": 85.5,
  "total_pairs": 5,
  "answered_pairs": 4,
  "unanswered_pairs": 1,
  "conversation": [
    {
      "role": "assistant",
      "text": "Hello, how can I help you today?",
      "created_at": 1743049201.234
    },
    {
      "role": "user",
      "text": "I need help with my account",
      "created_at": 1743049203.456
    }
  ],
  "qa_pairs": [
    {
      "question": "What is your account number?",
      "question_at": 1743049205.678,
      "answer": "It's 12345",
      "answer_at": 1743049208.901,
      "score": 90,
      "matched_keywords": ["account", "number"],
      "question_keywords": ["account", "number"],
      "answer_keywords": ["12345"],
      "notes": "Answer captured."
    }
  ]
}
```

#### 4.2 Get Latest Analysis Summary
**GET /call/analysis/latest/summary**  
Retrieves a summarized version of the latest call analysis.

**Response:**
```json
{
  "analysis_id": 42,
  "backend": "sqlite",
  "room_name": "outbound_1234567890",
  "participant_identity": "sip:1234567890",
  "participant_kind": "sip_participant",
  "started_at": 1743049200.123,
  "ended_at": 1743049260.456,
  "duration_seconds": 60.333,
  "close_reason": "participant_left",
  "overall_match_score": 85.5,
  "total_pairs": 5,
  "answered_pairs": 4,
  "unanswered_pairs": 1
}
```

#### 4.3 Get Analysis by ID
**GET /call/analysis/{analysis_id}**  
Retrieves a specific call analysis by its numeric ID.

**Path Parameters:**
- `analysis_id` (integer): The analysis ID to retrieve

**Response:** Same format as `/call/analysis/latest`

**Example:**
```bash
curl "http://localhost:8000/call/analysis/42"
```

#### 4.4 Analysis Health Check
**GET /call/analysis/health**  
Checks the health of the call analysis database.

**Response:**
```json
{
  "backend": "sqlite",
  "status": "healthy",
  "details": {
    "total_analyses": 15,
    "latest_analysis_id": 42,
    "latest_analysis_age_seconds": 3600
  }
}
```

### 5. Webhook Endpoint
**POST /webhook/**  
LiveKit webhook endpoint for automatic agent spawning. This endpoint is called by LiveKit when room events occur.

**Request Headers:**
- `Content-Type: application/json`

**Request Body (example):**
```json
{
  "event": "room_started",
  "room": {
    "name": "test-room",
    "sid": "RM_abc123"
  }
}
```

**Response:**
```json
{
  "status": "received"
}
```

**Note:** For rooms starting with `outbound_`, the agent launch is skipped:
```json
{
  "status": "skipped"
}
```

## Error Handling

### HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad request (invalid parameters, configuration errors) |
| 404 | Resource not found (analysis ID doesn't exist) |
| 500 | Internal server error |

### Error Response Format
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Error Messages

1. **Configuration Errors:**
   - `"No LLM provider is configured. Set GOOGLE_API_KEY, OPENAI_API_KEY, and/or GROQ_API_KEY."`
   - `"Telephony STT is not configured. Set DEEPGRAM_API_KEY, or configure Google Cloud credentials..."`
   - `"Telephony TTS is not configured. Set CARTESIA_API_KEY with CARTESIA_VOICE_ID, or configure Google Cloud credentials..."`
   - `"VOBIZ_SIP_TRUNK_ID is not set in .env"`

2. **Resource Errors:**
   - `"No call analysis found"`
   - `"Call analysis not found"`

3. **Database Errors:**
   - `"Database connection failed"`

## Rate Limiting
Currently no rate limiting is implemented. For production use, consider implementing rate limiting based on your requirements.

## CORS
CORS is not configured by default. For web client access, configure CORS middleware in `main.py`.

## WebSocket Endpoints
The API does not expose WebSocket endpoints directly. WebSocket connections are handled by LiveKit servers using tokens generated by the `/token` endpoint.

## Testing the API

### Using curl
```bash
# Get token
curl "http://localhost:8000/token?room=test"

# Make outbound call
curl -X POST http://localhost:8000/call/outbound \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+1234567890"}'

# Get latest analysis
curl "http://localhost:8000/call/analysis/latest"

# Get analysis health
curl "http://localhost:8000/call/analysis/health"
```

### Using Python
```python
import requests

BASE_URL = "http://localhost:8000"

# Get token
response = requests.get(f"{BASE_URL}/token", params={"room": "test-room"})
token = response.json()["token"]

# Make outbound call
response = requests.post(
    f"{BASE_URL}/call/outbound",
    json={"phone_number": "+1234567890"}
)
print(response.json())

# Get analysis
response = requests.get(f"{BASE_URL}/call/analysis/latest")
analysis = response.json()
```

## Integration Examples

### 1. Frontend Integration
```javascript
// Generate token for LiveKit connection
async function getToken(room, identity) {
  const response = await fetch(`/token?room=${room}&identity=${identity}`);
  const data = await response.json();
  return data.token;
}

// Initiate outbound call
async function makeCall(phoneNumber) {
  const response = await fetch('/call/outbound', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone_number: phoneNumber })
  });
  return response.json();
}
```

### 2. Monitoring Dashboard
```python
import requests
import time
from datetime import datetime

def monitor_calls():
    while True:
        try:
            # Check health
            health = requests.get("http://localhost:8000/call/analysis/health").json()
            
            # Get latest analysis
            analysis = requests.get("http://localhost:8000/call/analysis/latest/summary").json()
            
            print(f"[{datetime.now()}] Health: {health['status']}, "
                  f"Latest score: {analysis.get('overall_match_score', 'N/A')}")
                  
        except Exception as e:
            print(f"Error: {e}")
            
        time.sleep(60)  # Check every minute
```

### 3. Automated Testing
```python
import pytest
import requests

@pytest.fixture
def api_client():
    return requests.Session()

def test_token_generation(api_client):
    response = api_client.get("http://localhost:8000/token", params={"room": "test"})
    assert response.status_code == 200
    assert "token" in response.json()

def test_outbound_call_missing_number(api_client):
    response = api_client.post("http://localhost:8000/call/outbound", json={})
    assert response.status_code == 422  # Validation error
```

## Webhook Configuration

### LiveKit Webhook Setup
To enable automatic agent spawning, configure LiveKit webhooks to point to your backend:

1. **Webhook URL:** `https://your-domain.com/webhook/`
2. **Events to send:** `room_started`
3. **Secret:** (optional) Add signature verification

### Webhook Payload Example
```json
{
  "event": "room_started",
  "room": {
    "name": "customer-support-123",
    "sid": "RM_abc123",
    "creation_time": "2024-03-27T07:30:00Z",
    "empty_timeout": 300,
    "max_participants": 20,
    "metadata": ""
  }
}
```

### Webhook Response Codes
- `200`: Webhook processed successfully
- `400`: Invalid webhook payload
- `500`: Internal server error processing webhook

## Database Schema

### Call Analyses Table
```sql
CREATE TABLE call_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room_name TEXT NOT NULL,
    participant_identity TEXT,
    participant_kind TEXT,
    started_at REAL NOT NULL,
    ended_at REAL NOT NULL,
    duration_seconds REAL NOT NULL,
    close_reason TEXT NOT NULL,
    overall_match_score REAL NOT NULL,
    total_pairs INTEGER NOT NULL,
    answered_pairs INTEGER NOT NULL,
    unanswered_pairs INTEGER NOT NULL,
    analysis_json TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Conversation Items Table
```sql
CREATE TABLE call_conversation_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    item_index INTEGER NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at REAL,
    extra_json TEXT,
    FOREIGN KEY (analysis_id) REFERENCES call_analyses(id) ON DELETE CASCADE
);
```

### QA Scores Table
```sql
CREATE TABLE call_qa_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    pair_index INTEGER NOT NULL,
    question TEXT NOT NULL,
    question_at REAL,
    answer TEXT,
    answer_at REAL,
    score REAL NOT NULL,
    matched_keywords_json TEXT NOT NULL,
    question_keywords_json TEXT NOT NULL,
    answer_keywords_json TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (analysis_id) REFERENCES call_analyses(id) ON DELETE CASCADE
);
```

## Performance Considerations

### Response Times
- **Token generation:** < 50ms
- **Outbound call initiation:** 1-3 seconds (includes SIP dialing)
- **Analysis retrieval:** < 100ms for latest, < 200ms by ID
- **Webhook processing:** < 100ms

### Caching
No caching is currently implemented. Consider adding caching for:
- Token generation (short-lived, 5-10 minutes)
- Analysis data (if frequently accessed)

### Pagination
Analysis endpoints don't currently support pagination. For large datasets, consider adding:
- `limit` and `offset` parameters to analysis endpoints
- Cursor-based pagination for better performance