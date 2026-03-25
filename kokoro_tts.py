import numpy as np
from pipecat.frames.frames import TTSSpeakFrame, AudioRawFrame
from pipecat.processors.frame_processor import FrameProcessor
from kokoro import KPipeline

class KokoroTTSService(FrameProcessor):
    def __init__(self, voice: str = "af_heart", lang_code: str = "a"):
        super().__init__()
        self.pipeline = KPipeline(lang_code=lang_code)
        self.voice = voice
        self.sample_rate = 24000

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)

        if isinstance(frame, TTSSpeakFrame):
            text = frame.text.strip()
            if not text:
                return

            # Generate audio using KPipeline
            generator = self.pipeline(text, voice=self.voice, speed=1.0)

            for i, (gs, ps, audio) in enumerate(generator):
                if audio is not None:
                    audio_frame = AudioRawFrame(
                        audio=audio.tobytes(),
                        sample_rate=self.sample_rate,
                        num_channels=1
                    )
                    await self.push_frame(audio_frame)