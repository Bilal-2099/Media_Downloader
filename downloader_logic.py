import os
import re
import sys
import time
import random
import shutil
import smtplib
import requests
import subprocess
import yt_dlp
import instaloader
from io import BytesIO
from PIL import Image
from urllib.parse import urlparse
from email.message import EmailMessage

L = instaloader.Instaloader(
    download_pictures=True, 
    download_videos=True, 
    save_metadata=False,
    download_geotags=False
)

def save_image_from_url(url, folder, name, notification):
    """
    Downloads raw bytes from a URL, converts them to a clean PNG using Pillow,
    and saves to the local disk.
    """
    try:
        # User-Agent header helps avoid basic bot blocks
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=20)
        res.raise_for_status()

        save_path = os.path.join(folder, f"{name}.png")
        
        # Using BytesIO to handle image in memory before saving
        with Image.open(BytesIO(res.content)) as img:
            img.convert("RGB").save(save_path, "PNG")
        
        print(f"✅ Photo saved: {save_path}")
        return save_path
    except Exception as e:
        print(f"❌ Image Processing Error: {e}")

# --- CORE DOWNLOADING LOGIC ---

def download_photo(url, notification):
    """
    Routes the URL to the best specialized scraper for photos/slideshows.
    """
    folder = os.path.abspath(os.path.join("downloads", "photos"))
    os.makedirs(folder, exist_ok=True)
    
    # CASE 1: TikTok (Using gallery-dl via subprocess for high-res slideshows)
    if "tiktok.com" in url.lower():
        print("🎵 TikTok detected. Using gallery-dl (Flattened mode)...")
        # -D forces gallery-dl to save directly in the target folder without sub-dirs
        command = [
            sys.executable, "-m", "gallery_dl",
            "-D", folder,
            "--filter", "extension not in ('mp3', 'm4a', 'wav', 'mp4')",
            url
        ]
        try:
            # We capture_output to keep the terminal clean
            subprocess.run(command, check=True, capture_output=True)
            print(f"✅ TikTok content synced to: {folder}")
        except Exception as e:
            print(f"⚠️ gallery-dl error: {e}")

    # CASE 2: Instagram (Using Instaloader to bypass 'Login Walls')
    elif "instagram.com" in url.lower():
        print("📸 Instagram detected. Extracting via Instaloader...")
        # Regex to pull the unique ID (shortcode) from the URL
        match = re.search(r"/(?:p|reels|reel)/([A-Za-z0-9_-]+)", url)
        if match:
            try:
                shortcode = match.group(1)
                post = instaloader.Post.from_shortcode(L.context, shortcode)
                save_image_from_url(post.url, folder, f"insta_{shortcode}", notification)
            except Exception as e:
                print(f"⚠️ Instaloader failed: {e}")

    # CASE 3: General Web (Pinterest, Unsplash, Direct links)
    else:
        print("🌐 Generic URL detected. Using standard Request...")
        save_image_from_url(url, folder, f"direct_{abs(hash(url))}", notification)

def download_video_audio(url, mode, notification):
    """
    Uses yt-dlp to handle complex video/audio streaming protocols.
    """
    base_folder = os.path.join("downloads", mode)
    os.makedirs(base_folder, exist_ok=True)

    # yt-dlp Options: configures quality and file paths
    ydl_opts = {
        "outtmpl": os.path.join(base_folder, "%(title)s.%(ext)s"),
        "ffmpeg_location": "./ffmpeg/bin",  # Path to your local ffmpeg binaries
        "quiet": True,
        "no_warnings": True,
    }

    # Audio Mode: Extract MP3
    if mode == "audio":
        ydl_opts.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        })
    # Video Mode: Best MP4
    else:
        ydl_opts.update({
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        })

    try:
        print(f"🚀 Fetching {mode} via yt-dlp...")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print(f"✅ Done! Check the '{base_folder}' directory.")
    except Exception as e:
        print(f"yt-dlp Error: {e}")

# --- ENTRY POINT ---

if __name__ == "__main__":
    print("\n" + "="*30)
    print("UNIVERSAL MEDIA DOWNLOADER")
    print("="*30)
    
    user_url = input("Paste URL: ").strip()
    user_type = input("Select Type (video / audio / photo): ").strip().lower()
    
    if user_type == "photo":
        download_photo(user_url)
    elif user_type in ["video", "audio"]:
        download_video_audio(user_url, user_type)
    else:
        print("Invalid type selected. Please choose video, audio, or photo.")