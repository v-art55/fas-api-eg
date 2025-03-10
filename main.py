from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import yt_dlp
import requests
import logging
import random
from time import sleep
from urllib.parse import unquote

app = FastAPI()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of modern user agents to rotate
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def get_audio_stream_url(video_url, request: Request = None):
   
    
    username = os.environ.get('YOUTUBE_USERNAME')
    password = os.environ.get('YOUTUBE_PASSWORD')
    
    if not username or not password:
        raise ValueError("YouTube credentials not configured")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'noplaylist': True,
        'extract_flat': False,
        'skip_download': True,
        'username': username,
        'password': password,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    # Add a random sleep to mimic human behavior
    sleep(random.uniform(0.5, 2.0))
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # Try using invidious instances for YouTube content
            if "youtube.com" in video_url or "youtu.be" in video_url:
                video_id = None
                if "v=" in video_url:
                    video_id = video_url.split("v=")[-1].split("&")[0]
                elif "youtu.be/" in video_url:
                    video_id = video_url.split("youtu.be/")[-1].split("?")[0]
                
                if video_id:
                    # Try multiple alternative frontends
                    instances = [
                        f"https://invidious.snopyta.org/watch?v={video_id}",
                        f"https://piped.video/watch?v={video_id}",
                        f"https://vid.puffyan.us/watch?v={video_id}"
                    ]
                    
                    for instance in instances:
                        logger.info(f"Trying alternative instance: {instance}")
                        try:
                            info = ydl.extract_info(instance, download=False)
                            if info and 'url' in info:
                                stream_url = info['url']
                                format = info.get('ext', 'mp3')
                                return stream_url, f"audio/{format}"
                        except Exception as e:
                            logger.warning(f"Instance {instance} failed: {e}")
                            continue
                
            # If alternative instances fail or it's not YouTube, try directly
            logger.info(f"Trying direct extraction for: {video_url}")
            info = ydl.extract_info(video_url, download=False)
            
            if 'url' in info:
                stream_url = info['url']
                format = info.get('ext', 'mp3')
                return stream_url, f"audio/{format}"
            else:
                raise ValueError("No audio stream URL found in video info")
                
        except Exception as e:
            logger.error(f"Failed to extract audio from {video_url}: {e}")
            raise ValueError(f"Failed to extract audio stream URL: {e}")

def stream_audio(url):
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Range': 'bytes=0-',
        'Referer': 'https://www.google.com/',
        'Connection': 'keep-alive',
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with requests.get(url, stream=True, timeout=(5, 30), headers=headers) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=16384):
                    if chunk:
                        yield chunk
                return
        except requests.exceptions.RequestException as e:
            logger.warning(f"Streaming error (attempt {attempt + 1}/{max_retries}): {e}")
            sleep(random.uniform(1, 3))
    raise HTTPException(status_code=500, detail="Failed to stream audio after multiple attempts")

@app.get("/stream")
async def stream_audio_endpoint(video_url: str, request: Request):
    video_url = unquote(video_url)
    logger.info(f"Received request with video_url: {video_url}")
    try:
        stream_url, format = get_audio_stream_url(video_url, request)
        return StreamingResponse(stream_audio(stream_url), media_type=format)
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5001, workers=2)
