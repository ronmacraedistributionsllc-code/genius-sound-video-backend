from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import shutil
import uuid
import subprocess
import os
from pathlib import Path

app = FastAPI()

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# This is REQUIRED so the browser can download /outputs/file.mp4
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "status": "running",
        "name": "Genius Sound Video Backend",
        "qualities": ["480p", "1080p", "4k"],
        "routes": ["/health", "/create-video", "/outputs"]
    }

@app.get("/health")
def health():
    return {
        "ok": True,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "qualities": ["480p", "1080p", "4k"]
    }

def get_resolution(q: str):
    q = (q or "480p").lower().strip()
    if q in ("480p", "sd"):
        return 854, 480
    if q in ("4k", "2160p", "uhd"):
        return 3840, 2160
    return 1920, 1080

def file_ext(filename: str, fallback: str):
    ext = Path(filename or "").suffix.lower()
    return ext if ext else fallback

@app.post("/create-video")
async def create_video(
    image: UploadFile = File(...),
    audio: UploadFile = File(...),
    quality: str = Form("480p"),
    resolution: str = Form("")
):
    if shutil.which("ffmpeg") is None:
        raise HTTPException(status_code=500, detail="FFmpeg is not installed.")

    selected_quality = resolution or quality or "480p"
    width, height = get_resolution(selected_quality)

    job_id = uuid.uuid4().hex

    image_path = UPLOAD_DIR / f"{job_id}_image{file_ext(image.filename, '.jpg')}"
    audio_path = UPLOAD_DIR / f"{job_id}_audio{file_ext(audio.filename, '.mp3')}"
    output_path = OUTPUT_DIR / f"genius_sound_{job_id}_{selected_quality}.mp4"

    try:
        with open(image_path, "wb") as f:
            f.write(await image.read())

        with open(audio_path, "wb") as f:
            f.write(await audio.read())

        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},format=yuv420p"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-loop", "1",
            "-framerate", "30",
            "-i", str(image_path),
            "-i", str(audio_path),
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            "-movflags", "+faststart",
            str(output_path),
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=900
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "FFmpeg failed",
                    "stderr": result.stderr[-2500:]
                }
            )

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise HTTPException(
                status_code=500,
                detail="FFmpeg finished but no video file was created."
            )

        return {
            "ok": True,
            "quality": selected_quality,
            "download_url": f"/outputs/{output_path.name}",
            "filename": output_path.name
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Render timed out. Try 480p or a shorter audio file.")
