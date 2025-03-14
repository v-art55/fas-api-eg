import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import requests
import logging
import random
import json
from time import sleep
from urllib.parse import unquote, urlparse, parse_qs

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

# List of Piped API instances
PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://api.piped.projectsegfau.lt",
    "https://piped-api.garudalinux.org",
    "https://pipedapi.syncpundit.io"
]

# List of Invidious API instances
INVIDIOUS_INSTANCES = [
    "https://invidious.snopyta.org",
    "https://vid.puffyan.us",
    "https://inv.riverside.rocks",
    "https://invidio.xamh.de",
    "https://invidious.kavin.rocks"
]

def extract_video_id(video_url):
    """Extract YouTube video ID from various URL formats."""
    if not video_url:
        return None
        
    # For URLs like youtube.com/watch?v=VIDEO_ID
    if "youtube.com/watch" in video_url:
        parsed_url = urlparse(video_url)
        query_params = parse_qs(parsed_url.query)
        return query_params.get("v", [None])[0]
        
    # For URLs like youtu.be/VIDEO_ID
    elif "youtu.be/" in video_url:
        path = urlparse(video_url).path
        return path.strip("/")
        
    # For URLs that might already be IDs
    elif len(video_url) == 11 and "/" not in video_url and "." not in video_url:
        return video_url
        
    return None

def get_random_headers():
    """Generate random headers to avoid detection."""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://music.youtube.com',
        'Referer': 'https://music.youtube.com/',
        'Connection': 'keep-alive',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }

def try_piped_api(video_id):
    """Try to get audio stream URL from Piped API instances."""
    random.shuffle(PIPED_INSTANCES)  # Randomize the order to distribute load
    
    for instance in PIPED_INSTANCES:
        try:
            logger.info(f"Trying Piped instance: {instance}")
            api_url = f"{instance}/streams/{video_id}"
            
            response = requests.get(api_url, headers=get_random_headers(), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Get audio streams and sort by quality
                audio_streams = data.get("audioStreams", [])
                if not audio_streams:
                    logger.warning(f"No audio streams found on {instance}")
                    continue
                    
                # Sort by bitrate (higher first)
                audio_streams.sort(key=lambda x: int(x.get("bitrate", 0)), reverse=True)
                best_audio = audio_streams[0]
                
                logger.info(f"Found audio stream via Piped: {best_audio.get('url', '')[:50]}...")
                return best_audio.get("url"), best_audio.get("mimeType", "audio/mp3").split(";")[0]
                
        except Exception as e:
            logger.warning(f"Piped instance {instance} failed: {str(e)}")
            sleep(random.uniform(0.5, 1.5))
            continue
            
    logger.warning("All Piped instances failed")
    return None, None

def try_invidious_api(video_id):
    """Try to get audio stream URL from Invidious API instances."""
    random.shuffle(INVIDIOUS_INSTANCES)  # Randomize the order to distribute load
    
    for instance in INVIDIOUS_INSTANCES:
        try:
            logger.info(f"Trying Invidious instance: {instance}")
            api_url = f"{instance}/api/v1/videos/{video_id}"
            
            response = requests.get(api_url, headers=get_random_headers(), timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Get audio formats
                audio_formats = [f for f in data.get("adaptiveFormats", []) 
                               if f.get("type", "").startswith("audio")]
                               
                if not audio_formats:
                    logger.warning(f"No audio formats found on {instance}")
                    continue
                    
                # Sort by bitrate (higher first)
                audio_formats.sort(key=lambda x: int(x.get("bitrate", 0)), reverse=True)
                best_audio = audio_formats[0]
                
                logger.info(f"Found audio stream via Invidious: {best_audio.get('url', '')[:50]}...")
                return best_audio.get("url"), best_audio.get("type", "audio/mp4").split(";")[0]
                
        except Exception as e:
            logger.warning(f"Invidious instance {instance} failed: {str(e)}")
            sleep(random.uniform(0.5, 1.5))
            continue
            
    logger.warning("All Invidious instances failed")
    return None, None

def get_audio_stream_url(video_url):
    """Get audio stream URL using multiple methods."""
    # Extract video ID from URL
    video_id = extract_video_id(video_url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {video_url}")
        
    logger.info(f"Extracted video ID: {video_id}")
    
    # Add a small random delay to mimic human behavior
    sleep(random.uniform(0.2, 1.0))
    
    # Try Piped API first
    stream_url, content_type = try_piped_api(video_id)
    if stream_url:
        return stream_url, content_type
        
    # If Piped fails, try Invidious API
    stream_url, content_type = try_invidious_api(video_id)
    if stream_url:
        return stream_url, content_type
        
    # If all methods fail, raise an error
    raise ValueError("Failed to get audio stream URL from all services")

def stream_audio(url):
    """Stream audio from the given URL."""
    headers = {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.5',
        'Range': 'bytes=0-',
        'Referer': 'https://music.youtube.com/',
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
    """Endpoint to stream audio from a video URL."""
    video_url = unquote(video_url)
    logger.info(f"Received request with video_url: {video_url}")
    
    try:
        stream_url, content_type = get_audio_stream_url(video_url)
        logger.info(f"Streaming with content type: {content_type}")
        return StreamingResponse(stream_audio(stream_url), media_type=content_type)
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "audio-streaming-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5001, workers=2)
