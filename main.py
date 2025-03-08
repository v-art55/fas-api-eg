from fastapi import FastAPI, HTTPException
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
        'format': 'bestaudio/best',  # Extract the best audio format
        'quiet': True,               # Suppress output
        'noplaylist': True,          # Avoid downloading playlists
        'extract_flat': False,       # Ensure full metadata extraction
        'skip_download': True,       # Skip downloading the file
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            # Extract video info
            info = ydl.extract_info(video_url, download=False)
            
            # Get the audio stream URL
            if 'url' in info:
                stream_url = info['url']
                format = info.get('ext', 'audio/mpeg')  # Default to 'audio/mpeg'
                return stream_url, f"audio/{format}"
            else:
                raise ValueError("No audio stream URL found in video info")
        except Exception as e:
            raise ValueError(f"Error extracting stream URL: {e}")

def stream_audio(url):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with requests.get(url, stream=True, timeout=(3, 5)) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=16384):  # Stream in 16KB chunks
                    if chunk:
                        yield chunk
                return
        except requests.exceptions.RequestException as e:
            logger.warning(f"Streaming error (attempt {attempt + 1}/{max_retries}): {e}")
            sleep(1)  # Wait before retrying
    raise HTTPException(status_code=500, detail="Failed to stream audio")

@app.get("/stream")
async def stream_audio_endpoint(video_url: str):
    video_url = unquote(video_url)  # Decode URL-encoded string
    logger.info(f"Received request with video_url: {video_url}")
    try:
        # Modify the video URL to use Piped
        if "youtube.com" in video_url or "youtu.be" in video_url:
            video_id = video_url.split("v=")[-1].split("&")[0]  # Extract video ID
            video_url = f"https://piped.video/watch?v={video_id}"  # Convert to Piped URL
        
        # Get the audio stream URL
        stream_url, format = get_audio_stream_url(video_url)
        return StreamingResponse(stream_audio(stream_url), media_type=format)
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5001, workers=4)
