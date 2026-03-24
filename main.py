from fastapi import FastAPI
from kokoro_tts import synthesize_speech
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the FastAPI server with Pipecat pipeline!"}

@app.post("/tts")
def tts_endpoint(text: str):
    audio_path = synthesize_speech(text)
    return {"audio_path": audio_path}

# Placeholder for Pipecat pipeline integration
# def run_pipecat_pipeline(...):
#     pass
