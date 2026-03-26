import asyncio
import logging
import os

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import Agent, AgentSession, JobContext, JobProcess, WorkerOptions, cli, llm, room_io
from livekit.agents.utils import wait_for_participant, wait_for_track_publication
from livekit.plugins import deepgram, google, noise_cancellation, openai, silero

try:
    from livekit.plugins import cartesia
except ImportError:
    cartesia = None

load_dotenv()

logger = logging.getLogger("telephony-agent")
logger.setLevel(logging.INFO)


def _has_google_cloud_credentials() -> bool:
    credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_CLOUD_CREDENTIALS_FILE")
    return bool(credentials_file and os.path.exists(credentials_file))


def _build_llm() -> llm.LLM:
    providers: list[llm.LLM] = []
    preferred = os.getenv("PRIMARY_LLM_PROVIDER", "google").strip().lower()

    google_api_key = os.getenv("GOOGLE_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if google_api_key:
        providers.append(
            google.LLM(
                model=os.getenv("GOOGLE_GEMINI_MODEL", "gemini-2.5-flash"),
                api_key=google_api_key,
            )
        )

    if openai_api_key:
        providers.append(
            openai.LLM(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                api_key=openai_api_key,
            )
        )

    if not providers:
        raise RuntimeError(
            "No LLM provider is configured. Set GOOGLE_API_KEY and/or OPENAI_API_KEY."
        )

    providers.sort(key=lambda provider: 0 if provider.label.startswith(f"livekit.plugins.{preferred}") else 1)

    provider_names = [provider.label for provider in providers]
    logger.info("using LLM fallback chain: %s", " -> ".join(provider_names))

    if len(providers) == 1:
        return providers[0]

    return llm.FallbackAdapter(
        llm=providers,
        attempt_timeout=float(os.getenv("LLM_ATTEMPT_TIMEOUT", "8")),
        max_retry_per_llm=0,
        retry_interval=float(os.getenv("LLM_RETRY_INTERVAL", "0.5")),
        retry_on_chunk_sent=False,
    )


def prewarm(proc: JobProcess) -> None:
    """Load VAD once per worker process to keep call startup fast."""
    proc.userdata["vad"] = silero.VAD.load()


class TelephonyAssistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
You are a helpful, friendly, and professional AI phone assistant.
Speak naturally, clearly, and concisely.
Keep responses short and phone-friendly.
Use a warm, polite tone and guide the caller efficiently.
If the caller asks for a human agent, say you will transfer them and end politely.
""".strip()
        )


async def _wait_for_call_participant(room: rtc.Room) -> rtc.RemoteParticipant:
    participant = await wait_for_participant(room)

    try:
        await wait_for_track_publication(
            room,
            identity=participant.identity,
            kind=rtc.TrackKind.KIND_AUDIO,
        )
    except Exception:
        logger.exception("failed while waiting for participant audio track")

    if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        for _ in range(40):
            call_status = participant.attributes.get("sip.callStatus", "").lower()
            if call_status not in {"", "dialing", "ringing"}:
                break
            await asyncio.sleep(0.5)

        await asyncio.sleep(0.5)

    return participant


def _build_stt(is_phone_call: bool):
    if os.getenv("DEEPGRAM_API_KEY"):
        model = "nova-2-phonecall" if is_phone_call else "nova-2-general"
        logger.info("using Deepgram STT with model %s", model)
        return deepgram.STT(model=model)

    if _has_google_cloud_credentials():
        logger.info("using Google Cloud STT")
        return google.STT()

    raise RuntimeError(
        "No telephony STT provider is configured. Set DEEPGRAM_API_KEY or GOOGLE_APPLICATION_CREDENTIALS. GOOGLE_API_KEY alone cannot be used for Google STT."
    )


def _build_tts():
    cartesia_api_key = os.getenv("CARTESIA_API_KEY")
    cartesia_voice_id = os.getenv("CARTESIA_VOICE_ID")
    if cartesia and cartesia_api_key and cartesia_voice_id:
        logger.info("using Cartesia TTS voice %s", cartesia_voice_id)
        return cartesia.TTS(voice=cartesia_voice_id)

    if _has_google_cloud_credentials():
        google_voice = os.getenv("GOOGLE_TTS_VOICE", "en-US-Neural2-F")
        logger.info("using Google TTS voice %s", google_voice)
        return google.TTS(voice_name=google_voice)

    raise RuntimeError(
        "No telephony TTS provider is configured. Set CARTESIA_API_KEY with CARTESIA_VOICE_ID, or configure GOOGLE_APPLICATION_CREDENTIALS for Google TTS."
    )


async def entrypoint(ctx: JobContext) -> None:
    logger.info("new telephony job started - room=%s", ctx.room.name)

    await ctx.connect()
    participant = await _wait_for_call_participant(ctx.room)
    is_phone_call = participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP

    room_options = room_io.RoomOptions(
        audio_input=room_io.AudioInputOptions(
            noise_cancellation=lambda params: (
                noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC()
            ),
        ),
    )

    session = AgentSession(
        stt=_build_stt(is_phone_call=is_phone_call),
        llm=_build_llm(),
        tts=_build_tts(),
        vad=ctx.proc.userdata.get("vad") or silero.VAD.load(),
    )

    await session.start(
        room=ctx.room,
        agent=TelephonyAssistant(),
        room_options=room_options,
    )

    try:
        await session.generate_reply(
            instructions="Greet the caller warmly and ask how you can help them today.",
            allow_interruptions=True,
        )
    except Exception:
        logger.exception("failed to generate initial greeting")


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )
