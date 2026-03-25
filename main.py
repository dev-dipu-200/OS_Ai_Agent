import os
import asyncio
import subprocess
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask

# Correct imports for Pipecat 0.0.107
from pipecat.services.ollama.llm import OLLamaLLMService
from pipecat.services.whisper.stt import WhisperSTTService
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)

# LiveKit imports
from livekit import api

# Your custom Kokoro TTS
from kokoro_tts import KokoroTTSService
from outbound_call import make_outbound_call
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="TeleCMI AI Voice Agent")

class CallRequest(BaseModel):
    phone_number: str

# ================== CUSTOMIZE YOUR AGENT ==================
SYSTEM_PROMPT = """
You are a polite, professional, and friendly AI voice agent for [YOUR BUSINESS NAME] in India.
Speak naturally in Hindi or English (Hinglish is fine).
Be helpful and keep the conversation flowing for up to 10 minutes.
If the user wants to speak to a human, say "Transferring you to our team member" and end politely.
"""

@app.get("/")
async def home():
    return HTMLResponse(
        "<h1>✅ AI Voice Agent Server is Running</h1>"
        "<p>WebSocket endpoint: <code>/ws/telecmi</code></p>"
        "<p>LiveKit is enabled.</p>"
    )

@app.get("/token")
async def get_token(room: str = "default-room", identity: str = "ai-agent"):
    """
    Generate a LiveKit token for the agent or client to join a room.
    """
    token = api.AccessToken(
        os.getenv("LIVEKIT_API_KEY"),
        os.getenv("LIVEKIT_API_SECRET")
    ) \
        .with_identity(identity) \
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room,
        ))
    return {"token": token.to_jwt()}

@app.post("/webhook")
async def livekit_webhook(request: Request):
    """
    Handle LiveKit webhooks to auto-start the agent when a room is created.
    """
    try:
        # Note: In production, you should verify the webhook signature
        # using livekit.api.WebhookReceiver
        body = await request.body()
        body_str = body.decode('utf-8')
        # For simple debugging, let's just log and try to parse
        print(f"🔔 Received Webhook from LiveKit")
        print(f"📦 Webhook Body: {body_str}")
        
        # LiveKit sends a signed JWT in the 'Authorization' header or as a raw body
        # For now, we assume simple JSON for initial testing if configured that way
        try:
            data = await request.json()
            event = data.get("event")
            room_name = data.get("room", {}).get("name")
            print(f"🔹 Event: {event}, Room: {room_name}")
            
            if event == "room_started" and room_name:
                # 🛑 IMPORTANT: Skip auto-starting agent for outbound calls
                # because outbound_call.py already starts its own agent.
                if room_name.startswith("outbound_"):
                    print(f"⏭️ Skipping auto-agent for outbound room: {room_name}")
                    return {"status": "skipped"}

                print(f"🚀 Room started: {room_name}. Launching AI Agent...")
                # Use the new framework's 'connect' command
                # It will automatically use LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET from .env
                subprocess.Popen(["python", "livekit_agent.py", "connect", "--room", room_name])
        except Exception as e:
            print(f"⚠️ Webhook body was not plain JSON or error parsing: {e}")
            
        print(f"✅ Webhook processed successfully")
        return {"status": "received"}
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        return {"status": "error"}

@app.post("/call")
async def call_user(request: CallRequest):
    """
    Initiate an outbound call to a phone number.
    """
    try:
        print(f"📞 API Request to call {request.phone_number}")
        # Call the separate function
        await make_outbound_call(request.phone_number)
        return {"status": "success", "message": f"Call initiated to {request.phone_number}"}
    except Exception as e:
        print(f"❌ Error initiating call: {e}")
        return {"status": "error", "message": str(e)}

@app.websocket("/ws/telecmi")
async def telecmi_websocket(websocket: WebSocket):
    await websocket.accept()
    call_id = "unknown"

    try:
        initial_data = await websocket.receive_json()
        call_id = initial_data.get("call_id") or initial_data.get("stream_id", "unknown")

        print(f"📞 New TeleCMI call received - Call ID: {call_id}")

        transport = FastAPIWebsocketTransport(
            websocket=websocket,
            params=FastAPIWebsocketParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                add_wav_header=False,
            ),
        )

        stt = WhisperSTTService(
            settings=WhisperSTTService.Settings(
                model="small",
                language="hi",
            )
        )

        llm = OLLamaLLMService(model="llama3.2", base_url="http://localhost:11434/v1")
        tts = KokoroTTSService(voice="af_heart")

        pipeline = Pipeline([
            transport.input(),
            stt,
            llm,
            tts,
            transport.output(),
        ])

        await llm.set_messages([{"role": "system", "content": SYSTEM_PROMPT}])

        # ✅ Create PipelineRunner inside the async websocket handler
        runner = PipelineRunner()
        task = PipelineTask(pipeline)

        print(f"🚀 Starting AI agent for call {call_id}")
        await runner.run(task)

    except WebSocketDisconnect:
        print(f"Call ended - Call ID: {call_id}")
    except Exception as e:
        print(f"❌ Error in call {call_id}: {e}")
    finally:
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        log_level="info"
    )