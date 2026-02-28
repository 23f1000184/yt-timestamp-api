import os
import uuid
import time
from fastapi import FastAPI
from pydantic import BaseModel
import yt_dlp
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

app = FastAPI()

class AskRequest(BaseModel):
    video_url: str
    topic: str

def download_audio(url: str) -> str:
    filename = f"audio_{uuid.uuid4()}.mp3"

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": filename,
        "quiet": True,
        "noplaylist": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            }
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return filename

@app.post("/ask")
def ask(data: AskRequest):

    audio_path = download_audio(data.video_url)

    try:
        # Upload to Gemini Files API
        file = genai.upload_file(path=audio_path)

        # Wait until ACTIVE
        while file.state.name != "ACTIVE":
            time.sleep(2)
            file = genai.get_file(file.name)

        model = genai.GenerativeModel("gemini-2.0-flash")

        response = model.generate_content(
            [
                file,
                f"Find the FIRST timestamp where the topic '{data.topic}' is spoken. "
                "Return ONLY in HH:MM:SS format."
            ],
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "string"}
                    },
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
