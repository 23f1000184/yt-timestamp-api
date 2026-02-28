# force rebuild
import os
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
        file = genai.upload_file(path=audio_path)

        while file.state.name != "ACTIVE":
            time.sleep(2)
            file = genai.get_file(file.name)

        model = genai.GenerativeModel("gemini-1.5-pro")
        
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
