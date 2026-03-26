import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from livekit import api
from pydantic import BaseModel
from call_analysis import fetch_latest_analysis, fetch_analysis_by_id, analysis_db_health
from outbound_call import (
    make_outbound_call,
    start_agent_process,
    stop_agent_processes,
    validate_telephony_provider_config,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telephony-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    logger.info("FastAPI shutdown detected; stopping spawned AI agents")
    stop_agent_processes()


app = FastAPI(title="LiveKit Gemini Telephony Backend", lifespan=lifespan)


class CallRequest(BaseModel):
    phone_number: str


def _launch_agent(room_name: str) -> None:
    validate_telephony_provider_config()
    logger.info("launching livekit agent for room=%s", room_name)
    start_agent_process(room_name)


@app.get("/")
async def home():
    return HTMLResponse(
        "<h1>LiveKit Gemini Telephony Backend</h1>"
        "<p>Outbound call endpoint: <code>POST /call/outbound</code></p>"
        "<p>Legacy alias: <code>POST /call</code></p>"
        "<p>Token endpoint: <code>GET /token</code></p>"
    )


@app.get("/token")
async def get_token(room: str = "default-room", identity: str = "ai-agent"):
    token = (
        api.AccessToken(
            os.getenv("LIVEKIT_API_KEY"),
            os.getenv("LIVEKIT_API_SECRET"),
        )
        .with_identity(identity)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
            )
        )
    )
    return {"token": token.to_jwt()}


@app.post("/webhook/")
async def livekit_webhook(request: Request):
    try:
        logger.info("received LiveKit webhook")
        try:
            data = await request.json()
            event = data.get("event")
            room_name = data.get("room", {}).get("name")

            if event == "room_started" and room_name:
                if room_name.startswith("outbound_"):
                    logger.info("skipping auto-agent for outbound room=%s", room_name)
                    return {"status": "skipped"}

                _launch_agent(room_name)
        except Exception as exc:
            logger.warning("unable to parse webhook body as json: %s", exc)

        return {"status": "received"}
    except Exception as exc:
        logger.exception("webhook handling failed")
        return {"status": "error", "message": str(exc)}


@app.get("/call/analysis/latest")
async def latest_call_analysis():
    try:
        result = await fetch_latest_analysis()
        if result is None:
            raise HTTPException(status_code=404, detail="No call analysis found")
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/call/analysis/latest/summary")
async def latest_call_analysis_summary():
    try:
        result = await fetch_latest_analysis()
        if result is None:
            raise HTTPException(status_code=404, detail="No call analysis found")
        return {
            "analysis_id": result.get("_analysis_id"),
            "backend": result.get("_backend"),
            "room_name": result.get("room_name"),
            "participant_identity": result.get("participant_identity"),
            "participant_kind": result.get("participant_kind"),
            "started_at": result.get("started_at"),
            "ended_at": result.get("ended_at"),
            "duration_seconds": result.get("duration_seconds"),
            "close_reason": result.get("close_reason"),
            "overall_match_score": result.get("overall_match_score"),
            "total_pairs": result.get("total_pairs"),
            "answered_pairs": result.get("answered_pairs"),
            "unanswered_pairs": result.get("unanswered_pairs"),
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/call/analysis/{analysis_id}")
async def call_analysis_by_id(analysis_id: int):
    try:
        result = await fetch_analysis_by_id(analysis_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Call analysis not found")
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/call/analysis/health")
async def analysis_health():
    try:
        status = await analysis_db_health()
        return status
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/call/outbound")
async def call_user(request: CallRequest):
    try:
        logger.info("outbound call requested for %s", request.phone_number)
        await make_outbound_call(request.phone_number)
        return {
            "status": "success",
            "message": f"Call initiated to {request.phone_number}",
        }
    except RuntimeError as exc:
        logger.exception("invalid outbound call configuration")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("error initiating outbound call")
        raise HTTPException(
            status_code=500, detail="Failed to initiate outbound call"
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        log_level="info",
    )
