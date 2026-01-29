# Media Downloader (FastAPI + Docker)
A robust, containerized web application that allows users to download photos, videos, and audio from popular social media platforms (TikTok, Instagram, YouTube, etc.) using a clean web interface.

## Features
-   **Multi-Platform Support**: Downloads content using `yt-dlp`, `gallery-dl`, and `instaloader`.
-   **Flexible Formats**: Choose between High-Quality Video, MP3 Audio, or Image files.
-   **Dockerized Environment**: No need to manually install FFmpeg or Python dependencies.
-   **Smart Cleanup**: Automatically deletes temporary files from the server after the download is complete to save disk space.
-   **FastAPI Powered**: High-performance asynchronous backend.

## Tech Stack
* **Backend**: Python 3.11, FastAPI
* **Frontend**: HTML5, Jinja2 Templates
* **Tools**: FFmpeg, yt-dlp, gallery-dl, instaloader
* **Infrastructure**: Docker, Docker Compose

## Getting Started
### Prerequisites
* Docker installed and running.
* Virtualization enabled in BIOS (for Windows users).

### Installation & Running
1.  **Clone the project** to your local machine.
2.  **Open your terminal** in the project folder.
3.  **Run the application** using Docker Compose:

    ```bash
    docker compose up --build
    ```

4.  **Access the App**: Open your browser and go to:
    `http://localhost:8000`

## Project Structure

* `app.py`: FastAPI web server and routing logic.
* `downloader_logic.py`: Core logic for interacting with various download engines.
* `template/`: Contains the HTML frontend.
* `Dockerfile`: Instructions for building the Linux container.
* `compose.yaml`: Configuration for orchestrating the app services.

## Usage
1.  Paste the **URL** of the media you want to download.
2.  Select the **Format** (Video, Audio, or Photo).
3.  Click **Download**. The app will process the request and your browser will automatically start the download once it's ready.
