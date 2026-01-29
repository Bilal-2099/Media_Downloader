from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask
import os
import shutil
import tempfile
import asyncio
import glob
import zipfile
from pathlib import Path
import re
import sys
import subprocess
from io import BytesIO
import requests
from PIL import Image
import yt_dlp
import instaloader
import mimetypes
import base64
from urllib.parse import urlparse
from urllib.parse import quote as urlquote
import mimetypes
import base64

app = FastAPI()
templates = Jinja2Templates(directory="template")

try:
    _INSTALOADER = instaloader.Instaloader(
        download_pictures=True,
        download_videos=True,
        save_metadata=False,
        download_geotags=False,
    )
except Exception:
    _INSTALOADER = None


def _save_image_from_url(url: str, folder: str, name: str):
    """Download an image URL and save it as PNG into `folder` with `name`."""
    os.makedirs(folder, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()

    img = Image.open(BytesIO(resp.content))
    img_format = img.format

    fmt_to_ext = {
        'JPEG': '.jpg',
        'JPG': '.jpg',
        'PNG': '.png',
        'WEBP': '.webp',
        'GIF': '.gif',
        'BMP': '.bmp',
        'TIFF': '.tiff',
    }

    ext = None
    if img_format and img_format.upper() in fmt_to_ext:
        ext = fmt_to_ext[img_format.upper()]

    if not ext:
        path = urlparse(url).path
        _, uext = os.path.splitext(path)
        if uext:
            ext = uext.lower()

    if not ext:
        ctype = resp.headers.get('content-type', '')
        if ctype:
            guess = mimetypes.guess_extension(ctype.split(';')[0].strip())
            if guess == '.jpe':
                guess = '.jpg'
            ext = guess

    if not ext:
        ext = '.png'

    save_path = os.path.join(folder, f"{name}{ext}")

    ext_to_pil = {
        '.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG', '.webp': 'WEBP',
        '.gif': 'GIF', '.bmp': 'BMP', '.tiff': 'TIFF'
    }
    pil_format = ext_to_pil.get(ext.lower(), img_format or 'PNG')

    if pil_format in ('JPEG', 'PNG', 'WEBP', 'GIF', 'BMP', 'TIFF'):
        img.convert('RGB').save(save_path, pil_format)
    else:
        img.save(save_path)

    return save_path


def download_photo(url: str, notification: bool = False, target_folder: str | None = None):
    """Download photo(s) into target_folder and handle TikTok slideshows correctly."""
    if target_folder is None:
        folder = os.path.abspath(os.path.join("downloads", "photos"))
    else:
        folder = os.path.abspath(target_folder)
    os.makedirs(folder, exist_ok=True)

    lower = url.lower()
    
    # --- TIKTOK SLIDESHOW FIX ---
    if "tiktok.com" in lower:
        print(f"DEBUG: Attempting TikTok download for: {url}")
        command = [
            sys.executable, "-m", "gallery_dl",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "-D", folder,
            "--option", f"directory.base={folder}", 
            "--filter", "extension not in ('mp3', 'm4a', 'wav', 'mp4')",
            url,
        ]
        
        # Run and wait for it to finish
        try:
            subprocess.run(command, check=False, timeout=60)
        except subprocess.TimeoutExpired:
            print("DEBUG: gallery-dl timed out.")

        # 1. Search recursively for ANY files
        all_downloaded = glob.glob(os.path.join(folder, "**", "*"), recursive=True)
        files = [f for f in all_downloaded if os.path.isfile(f)]
        
        print(f"DEBUG: Files found on disk: {len(files)}")

        result = {}
        for f in files:
            # Skip non-images
            if not f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.jfif')):
                continue

            try:
                with Image.open(f) as im:
                    im.thumbnail((320, 320))
                    buf = BytesIO()
                    im.convert('RGB').save(buf, 'JPEG', quality=75)
                    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
                    result["thumbnail_b64"] = f"data:image/jpeg;base64,{b64}"
                    break 
            except Exception as e:
                print(f"DEBUG: Skipping {f} - {e}")
                continue
                
        # If result is still empty here, it means no valid images were processed
        return result

    # --- INSTAGRAM LOGIC ---
    if "instagram.com" in lower and _INSTALOADER is not None:
        m = re.search(r"/(?:p|reels|reel)/([A-Za-z0-9_-]+)", url)
        if m:
            try:
                shortcode = m.group(1)
                post = instaloader.Post.from_shortcode(_INSTALOADER.context, shortcode)
                if hasattr(post, "url") and post.url:
                    saved = _save_image_from_url(post.url, folder, f"insta_{shortcode}")
                    with Image.open(saved) as im:
                        im.thumbnail((320, 320))
                        buf = BytesIO()
                        im.convert('RGB').save(buf, 'JPEG', quality=75)
                        b64 = base64.b64encode(buf.getvalue()).decode('ascii')
                        return {"thumbnail_b64": f"data:image/jpeg;base64,{b64}"}
            except Exception:
                pass

    # --- GENERAL WEB ---
    saved = _save_image_from_url(url, folder, f"direct_{abs(hash(url))}")
    try:
        with Image.open(saved) as im:
            im.thumbnail((320, 320))
            buf = BytesIO()
            im.convert('RGB').save(buf, 'JPEG', quality=75)
            b64 = base64.b64encode(buf.getvalue()).decode('ascii')
            return {"thumbnail_b64": f"data:image/jpeg;base64,{b64}"}
    except Exception:
        return {}


def download_video_audio(url: str, mode: str, notification: bool = False, target_folder: str | None = None):
    """
    Fixed version: Improved reliability for YouTube and Playlists.
    """
    if target_folder is None:
        base_folder = os.path.abspath(os.path.join("downloads", mode))
    else:
        base_folder = os.path.abspath(target_folder)
    os.makedirs(base_folder, exist_ok=True)

    def progress_hook(d):
        if d["status"] == "downloading":
            p = d.get("_percent_str", "").strip()
            print(f"\r[Backend] Downloading: {p}", end="")

    ffmpeg_path = os.path.abspath("ffmpeg/bin")

    ydl_opts = {
        "outtmpl": os.path.join(base_folder, "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "ignoreerrors": True,
        "nocheckcertificate": True,
        "extractor_args": {'youtube': {'player_client': ['android', 'ios']}},
        "user_agent": "com.google.android.youtube/19.29.37 (Linux; U; Android 11) gzip",
        "http_headers": {
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        }
    }

    if os.path.exists(ffmpeg_path):
        ydl_opts["ffmpeg_location"] = ffmpeg_path

    if mode == "audio":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    else:
        ydl_opts.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "merge_output_format": "mp4",
        })

    # This is the blocking call
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # Process metadata (Playlist vs Single)
    result = {}
    if info:
        result["playlist_title"] = info.get("title") if "entries" not in info else info.get("title", "Playlist")
        
        # Get Thumbnail
        thumb = info.get('thumbnail') or (info.get('thumbnails')[-1]['url'] if info.get('thumbnails') else None)
        if thumb:
            try:
                r = requests.get(thumb, timeout=5)
                if r.status_code == 200:
                    with Image.open(BytesIO(r.content)) as im:
                        im.thumbnail((320, 320))
                        buf = BytesIO()
                        im.convert('RGB').save(buf, 'JPEG', quality=75)
                        result['thumbnail_b64'] = f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
            except: pass

    return result


def cleanup_temp(path: str):
    """Deletes the temporary directory after the file has been sent to the user."""
    if os.path.exists(path):
        shutil.rmtree(path)


def _sanitize_filename(name: str) -> str:
    """Replace characters that are unsafe for filenames and trim length."""
    if not name:
        return "download"
    s = re.sub(r'[\\/:*?"<>|]', '_', name)
    s = s.strip()[:160]
    return s

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

class MediaRequest(BaseModel):
    url: str
    mode: str
    notification: bool = False


@app.post("/download/media")
async def download_media(
    request: Request,
    req: MediaRequest,
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    if req.mode not in ("video", "audio", "photo"):
        raise HTTPException(status_code=400, detail="Invalid format selected.")

    tmpdir = tempfile.mkdtemp()
    
    try:
        playlist_meta = {}
        if req.mode == "photo":
            await asyncio.to_thread(download_photo, req.url, False, target_folder=tmpdir)
        else:
            playlist_meta = await asyncio.to_thread(download_video_audio, req.url, req.mode, False, target_folder=tmpdir)

        downloaded_files = [
            f for f in glob.glob(os.path.join(tmpdir, "**", "*"), recursive=True)
            if os.path.isfile(f) and not os.path.basename(f).lower().startswith('thumb')
        ]
        
        if not downloaded_files:
            raise Exception("No media was found or downloaded. Check the URL.")

        if len(downloaded_files) == 1:
            file_path = downloaded_files[0]
            filename = os.path.basename(file_path)
            media_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{urlquote(filename)}"}

            thumb_b64 = None
            if isinstance(playlist_meta, dict):
                thumb_b64 = playlist_meta.get('thumbnail_b64') or playlist_meta.get('thumbnail')
            if thumb_b64:
                headers['X-Thumbnail'] = thumb_b64

            return FileResponse(
                path=file_path,
                media_type=media_type,
                headers=headers,
                background=BackgroundTask(cleanup_temp, tmpdir)
            )
        
        zip_path = os.path.join(tmpdir, "downloaded_files.zip")
        with zipfile.ZipFile(zip_path, 'w') as z:
            for f in downloaded_files:
                arcname = os.path.relpath(f, tmpdir)
                z.write(f, arcname=arcname)

        if playlist_meta and playlist_meta.get("playlist_title"):
            zip_name = f"{_sanitize_filename(playlist_meta.get('playlist_title'))}.zip"
        else:
            zip_name = "downloaded_photos.zip"
        media_type = "application/zip"
        headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{urlquote(zip_name)}"}
        return FileResponse(
            path=zip_path,
            media_type=media_type,
            headers=headers,
            background=BackgroundTask(cleanup_temp, tmpdir)
        )

    except Exception as e:
        cleanup_temp(tmpdir)
        import traceback
        print(traceback.format_exc()) # This prints the full error to YOUR terminal
        raise HTTPException(status_code=500, detail=f"Downloader Error: {str(e)}")