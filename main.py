# force rebuild
import os
import time
from fastapi import FastAPI
from pydantic import BaseModel
import yt_dlp
import google.generativeai as genai
from dotenv import load_dotenv
from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

load_dotenv()

app = FastAPI()

class AskRequest(BaseModel):
    video_url: str
    topic: str


def download_audio(url: str) -> str:
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": "audio.%(ext)s",
        "quiet": True,
        "noplaylist": True,
        "postprocessors": []
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


@app.post("/ask")
def ask(data: AskRequest):
    audio_path = download_audio(data.video_url)

    try:
        file = client.files.upload(file=audio_path)

        while file.state != "ACTIVE":
            time.sleep(2)
            file = client.files.get(name=file.name)
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                file,
                f"Find the FIRST timestamp where the topic '{data.topic}' is spoken. "
                "Return ONLY in HH:MM:SS format."
            ],
            config={
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "object",
                    "properties": {"timestamp": {"type": "string"}},
                    "required": ["timestamp"]
                }
            }
        )
        
        timestamp = response.parsed["timestamp"]

        return {
            "timestamp": timestamp,
            "video_url": data.video_url,
            "topic": data.topic
        }

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)
