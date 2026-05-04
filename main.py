import os
import uuid
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

APP_NAME = "Genius Sound Video Backend"
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = FastAPI(title=APP_NAME)

# Allow your website to call this backend.
# For tighter security, replace "*" with your real domain later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


@app.get("/")
def root():
    return {
        "status": "running",
        "name": APP_NAME,
        "routes": ["/health", "/create-video"],
    }


@app.get("/health")
def health():
    ffmpeg_ok = shutil.which("ffmpeg") is not None
    return {"ok": True, "ffmpeg": ffmpeg_ok}


def save_upload(upload: UploadFile, folder: Path, prefix: str) -> Path:
    ext = Path(upload.filename or "").suffix.lower()
    if not ext:
        raise HTTPException(status_code=400, detail=f"{prefix} file needs an extension")
    out_path = folder / f"{prefix}_{uuid.uuid4().hex}{ext}"
    with out_path.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return out_path


def get_resolution(quality: str) -> tuple[int, int]:
    q = (quality or "1080p").lower().strip()
    if q in ["4k", "2160p", "uhd"]:
        return 3840, 2160
    return 1920, 1080


@app.post("/create-video")
async def create_video(
    image: UploadFile = File(...),
    audio: UploadFile = File(...),
    quality: str = Form("1080p"),
):
    """
    Upload a photo + MP3/WAV and get a 1080p or 4K MP4 video.
    Form fields:
      image: jpg/png/webp
      audio: mp3/wav/m4a
      quality: 1080p or 4k
    """

    if shutil.which("ffmpeg") is None:
        raise HTTPException(
            status_code=500,
            detail="FFmpeg is not installed on the server. Use Docker or add FFmpeg support.",
        )

    job_id = uuid.uuid4().hex
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    image_path = save_upload(image, job_dir, "image")
    audio_path = save_upload(audio, job_dir, "audio")

    width, height = get_resolution(quality)
    output_path = OUTPUT_DIR / f"genius_sound_video_{job_id}_{quality.lower()}.mp4"

    # Still image + audio into video, scaled/cropped to exact 16:9.
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},format=yuv420p"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=900,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Video render timed out.")

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "FFmpeg failed",
                "error": result.stderr[-3000:],
            },
        )

    return {
        "ok": True,
        "quality": quality,
        "download_url": f"/outputs/{output_path.name}",
        "filename": output_path.name,
    }


@app.get("/download/{filename}")
def download(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path), media_type="video/mp4", filename=filename)
