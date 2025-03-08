from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import yt_dlp
import requests
import logging
from time import sleep
from urllib.parse import unquote

app = FastAPI()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_audio_stream_url(video_url):
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'extract_flat': False,
        'skip_download': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(video_url, download=False)
            stream_url = info['url']
            
            return stream_url, "audio/mpeg"
        except Exception as e:
            raise ValueError(f"Error extracting stream URL: {e}")

def stream_audio(url):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with requests.get(url, stream=True, timeout=(3, 5)) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=16384):
                    if chunk:
                        yield chunk
                return
        except requests.exceptions.RequestException as e:
            logger.warning(f"Streaming error (attempt {attempt + 1}/{max_retries}): {e}")
            sleep(1)
    
    raise HTTPException(status_code=500, detail="Failed to stream audio")

@app.get("/api/stream")
async def stream_audio_endpoint(video_url: str):
    video_url = unquote(video_url)
    
    logger.info(f"Received request with video_url: {video_url}")
    try:
        stream_url, format = get_audio_stream_url(video_url)
        return StreamingResponse(stream_audio(stream_url), media_type=format)
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))
