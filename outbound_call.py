import asyncio
import logging
import os
import subprocess
from typing import Set

from dotenv import load_dotenv
from livekit import api

load_dotenv()

logger = logging.getLogger("telephony-outbound")
_ACTIVE_AGENT_PROCESSES: Set[subprocess.Popen] = set()


def has_google_cloud_credentials() -> bool:
    credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_CLOUD_CREDENTIALS_FILE")
    return bool(credentials_file and os.path.exists(credentials_file))


def has_cartesia_credentials() -> bool:
    return bool(os.getenv("CARTESIA_API_KEY") and os.getenv("CARTESIA_VOICE_ID"))


def validate_telephony_provider_config() -> None:
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GROQ_API_KEY")):
        raise RuntimeError(
            "No LLM provider is configured. Set GOOGLE_API_KEY, OPENAI_API_KEY, and/or GROQ_API_KEY."
        )

    if os.getenv("DEEPGRAM_API_KEY") or has_google_cloud_credentials():
        if has_cartesia_credentials() or has_google_cloud_credentials():
            return
        raise RuntimeError(
            "Telephony TTS is not configured. Set CARTESIA_API_KEY with CARTESIA_VOICE_ID, or configure Google Cloud credentials via GOOGLE_APPLICATION_CREDENTIALS."
        )

    raise RuntimeError(
        "Telephony STT is not configured. Set DEEPGRAM_API_KEY, or configure Google Cloud credentials via GOOGLE_APPLICATION_CREDENTIALS. GOOGLE_API_KEY alone is only enough for Gemini LLM."
    )


def start_agent_process(room_name: str) -> subprocess.Popen:
    validate_telephony_provider_config()
    logger.info("starting AI agent for room=%s", room_name)
    process = subprocess.Popen(["python", "livekit_agent.py", "connect", "--room", room_name])
    _ACTIVE_AGENT_PROCESSES.add(process)
    return process


def _discard_finished_processes() -> None:
    finished = {process for process in _ACTIVE_AGENT_PROCESSES if process.poll() is not None}
    _ACTIVE_AGENT_PROCESSES.difference_update(finished)


def stop_agent_processes(timeout: float = 5.0) -> None:
    _discard_finished_processes()
    for process in list(_ACTIVE_AGENT_PROCESSES):
        logger.info("stopping AI agent pid=%s", process.pid)
        process.terminate()

    for process in list(_ACTIVE_AGENT_PROCESSES):
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            logger.warning("force killing AI agent pid=%s", process.pid)
            process.kill()
            process.wait(timeout=timeout)
        finally:
            _ACTIVE_AGENT_PROCESSES.discard(process)


async def make_outbound_call(phone_number: str):
    """
    1. Starts the AI Agent in a new room.
    2. Uses LiveKit SIP API to dial the phone number via Vobiz.
    """
    validate_telephony_provider_config()
    sip_trunk_id = os.getenv("VOBIZ_SIP_TRUNK_ID")
    if not sip_trunk_id:
        raise RuntimeError("VOBIZ_SIP_TRUNK_ID is not set in .env")

    room_name = f"outbound_{phone_number.replace('+', '').replace(' ', '')}"
    start_agent_process(room_name)

    lkapi = api.LiveKitAPI(
        url=os.getenv("LIVEKIT_URL"),
        api_key=os.getenv("LIVEKIT_API_KEY"),
        api_secret=os.getenv("LIVEKIT_API_SECRET"),
    )

    logger.info("dialing %s via Vobiz", phone_number)
    try:
        sip_participant = await lkapi.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=sip_trunk_id,
                sip_call_to=phone_number,
                room_name=room_name,
            )
        )
        logger.info(
            "SIP call request sent successfully participant=%s room=%s",
            getattr(sip_participant, "participant_identity", None),
            room_name,
        )
    except Exception:
        logger.exception("failed to initiate outbound SIP call")
        raise
    finally:
        await lkapi.aclose()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        target_number = sys.argv[1]
        asyncio.run(make_outbound_call(target_number))
    else:
        print("Usage: python outbound_call.py <phone_number_with_country_code>")
        print("Example: python outbound_call.py +919999999999")
