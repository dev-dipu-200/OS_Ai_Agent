import os
import asyncio
import logging
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    ChatContext,
    JobContext,
    WorkerOptions,
    cli,
    room_io,
    tts,
)
from livekit.plugins import google, silero, noise_cancellation
from kokoro import KPipeline
from faster_whisper import WhisperModel
import numpy as np
import torch
from livekit.agents import stt, utils

load_dotenv()

logger = logging.getLogger("ai-agent")

# --- Local Whisper STT Implementation ---
class WhisperSTT(stt.STT):
    def __init__(self, model_size: str = "tiny"):
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=False, interim_results=False)
        )
        device = "cuda" if torch.cuda.is_available() else "cpu"
        # Using tiny model for speed and low memory
        self._model = WhisperModel(model_size, device=device, compute_type="int8")

    async def _recognize_impl(
        self,
        buffer: utils.AudioBuffer,
        *,
        language: stt.NotGivenOr[str] = stt.NOT_GIVEN,
        conn_options: stt.APIConnectOptions,
    ) -> stt.SpeechEvent:
        # Combine frames into a single buffer
        frame = rtc.combine_audio_frames(buffer)
        # Convert int16 to float32 as expected by faster-whisper
        audio_data = np.frombuffer(frame.data, dtype=np.int16).astype(np.float32) / 32768.0
        
        # Run transcription in a thread to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        segments, _ = await loop.run_in_executor(
            None, lambda: self._model.transcribe(audio_data, beam_size=5)
        )
        
        text = "".join([s.text for s in segments]).strip()
        
        return stt.SpeechEvent(
            type=stt.SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[stt.SpeechData(text=text, language=language or "en", confidence=1.0)],
        )

# Custom TTS for Kokoro to work with LiveKit's inference engine
class KokoroTTS(tts.TTS):
    def __init__(self, voice: str = "af_heart", lang_code: str = "a"):
        super().__init__(
            streaming_supported=True,
            sample_rate=24000,
            num_channels=1,
        )
        self._pipeline = KPipeline(lang_code=lang_code)
        self._voice = voice

    def synthesize(self, text: str) -> tts.SynthesizeStream:
        return KokoroStream(self, text)

class KokoroStream(tts.SynthesizeStream):
    def __init__(self, tts: KokoroTTS, text: str):
        super().__init__(tts, text)
        self._text = text
        self._tts = tts

    async def _run(self):
        generator = self._tts._pipeline(self._text, voice=self._tts._voice, speed=1.0)
        for _, _, audio in generator:
            if audio is not None:
                audio_int16 = (audio * 32767).astype(np.int16)
                self._push_audio(
                    rtc.AudioFrame(
                        data=audio_int16.tobytes(),
                        sample_rate=self._tts.sample_rate,
                        num_channels=self._tts.num_channels,
                        samples_per_channel=len(audio_int16)
                    )
                )
        self._mark_done()

class DefaultAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a polite, professional, and friendly AI voice agent for [YOUR BUSINESS NAME] in India.
Speak naturally in Hindi or English (Hinglish is fine).
Be helpful and keep the conversation flowing for up to 10 minutes.
If the user wants to speak to a human, say "Transferring you to our team member" and end politely.
"""
        )

    async def on_enter(self):
        await self.session.generate_reply(
            instructions="""Greet the user in Hindi/English (Hinglish). Example: "नमस्ते! मैं आपकी क्या मदद कर सकता हूँ?" """,
            allow_interruptions=True,
        )

async def entrypoint(ctx: JobContext):
    logger.info(f"🚀 AI Agent starting in room: {ctx.room.name}")

    # 1. Initialize Services
    # Using Google Gemini as the LLM
    llm_service = google.LLM(
        model="gemini-2.5-flash",
    )

    # Using Local Whisper for Speech-to-Text (No API key needed)
    stt_service = WhisperSTT(model_size="tiny")

    tts_service = KokoroTTS(voice="af_heart")

    # 2. Setup Session
    session = AgentSession(
        stt=stt_service,
        llm=llm_service,
        tts=tts_service,
        vad=silero.VAD.load(),
    )

    # 3. Define Room Options (for SIP noise cancellation)
    room_options = room_io.RoomOptions(
        audio_input=room_io.AudioInputOptions(
            noise_cancellation=lambda params: noise_cancellation.BVCTelephony() if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP else noise_cancellation.BVC(),
        ),
    )

    # Start the session
    await session.start(agent=DefaultAgent(), room=ctx.room, room_options=room_options)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
