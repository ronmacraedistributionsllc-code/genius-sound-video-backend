from __future__ import annotations

import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from imageio_ffmpeg import get_ffmpeg_exe

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

JOB_LOCK = threading.Lock()
JOBS: Dict[str, Dict[str, Any]] = {}

app = FastAPI(title="Genius Sound Command Center")


def safe_extension(filename: str) -> str:
    return Path(filename or "").suffix.lower().strip()


def save_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)


def set_job(job_id: str, **updates: Any) -> None:
    with JOB_LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(updates)
            JOBS[job_id]["updated_at"] = time.time()


def get_job(job_id: str) -> Dict[str, Any]:
    with JOB_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found. It may have expired after a restart.")
        return dict(job)


def parse_duration_seconds(audio_path: Path, ffmpeg_path: str) -> Optional[float]:
    # Use ffmpeg itself instead of ffprobe so Render only needs one bundled binary.
    command = [ffmpeg_path, "-hide_banner", "-i", str(audio_path)]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    text = (completed.stdout or "") + "\n" + (completed.stderr or "")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))


def cleanup_old_files(max_age_hours: int = 24) -> None:
    cutoff = time.time() - (max_age_hours * 3600)
    for folder in (UPLOAD_DIR, OUTPUT_DIR):
        for item in folder.glob("*"):
            try:
                if item.is_file() and item.stat().st_mtime < cutoff:
                    item.unlink(missing_ok=True)
            except Exception:
                pass


def run_ffmpeg_job(job_id: str, audio_path: Path, photo_path: Path, output_path: Path) -> None:
    try:
        cleanup_old_files()
        ffmpeg_path = get_ffmpeg_exe()
        duration = parse_duration_seconds(audio_path, ffmpeg_path)

        set_job(
            job_id,
            status="processing",
            progress=8,
            message="Preparing 4K FFmpeg render...",
            duration_seconds=duration,
        )

        video_filter = (
            "scale=3840:2160:force_original_aspect_ratio=decrease,"
            "pad=3840:2160:(ow-iw)/2:(oh-ih)/2:color=black,"
            "setsar=1,format=yuv420p"
        )

        duration_args = []
        if duration and duration > 0:
            # Important: -t makes the still-image video stop at the audio length.
            # Without this, some FFmpeg builds keep rendering the looped image forever.
            duration_args = ["-t", f"{duration + 0.05:.3f}"]

        command = [
            ffmpeg_path,
            "-hide_banner",
            "-y",
            "-framerate", "30",
            "-loop", "1",
            "-i", str(photo_path),
            "-i", str(audio_path),
            "-map", "0:v:0",
            "-map", "1:a:0",
            *duration_args,
            "-vf", video_filter,
            "-c:v", "libx264",
            "-profile:v", "high",
            "-preset", os.environ.get("VIDEO_PRESET", "ultrafast"),
            "-tune", "stillimage",
            "-x264-params", "rc-lookahead=10:ref=1:bframes=0",
            "-threads", os.environ.get("VIDEO_THREADS", "1"),
            "-crf", os.environ.get("VIDEO_CRF", "20"),
            "-r", "30",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "320k",
            "-shortest",
            "-movflags", "+faststart",
            "-nostats",
            "-progress", "pipe:1",
            str(output_path),
        ]

        last_lines = []
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        assert process.stdout is not None
        fake_progress = 8
        last_fake_update = time.time()

        for raw_line in process.stdout:
            line = raw_line.strip()
            if line:
                last_lines.append(line)
                last_lines = last_lines[-80:]

            if line.startswith("out_time_ms=") and duration and duration > 0:
                try:
                    out_time_ms = int(line.split("=", 1)[1])
                    current_seconds = out_time_ms / 1_000_000
                    percent = 10 + min(85, (current_seconds / duration) * 85)
                    set_job(job_id, status="processing", progress=round(percent, 1), message=f"Rendering 4K video... {round(percent)}%")
                except ValueError:
                    pass
            elif duration is None and time.time() - last_fake_update > 2:
                fake_progress = min(94, fake_progress + 2)
                last_fake_update = time.time()
                set_job(job_id, status="processing", progress=fake_progress, message="Rendering 4K video...")
            elif line == "progress=end":
                set_job(job_id, progress=96, message="Finalizing MP4 file...")

        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError("FFmpeg failed with exit code " + str(return_code) + ": " + " | ".join(last_lines[-12:]))

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("FFmpeg finished but no output file was created.")

        set_job(
            job_id,
            status="finished",
            progress=100,
            message="Finished. Your 4K video is ready.",
            output_filename=output_path.name,
            download_url=f"/download/{job_id}",
            file_size_bytes=output_path.stat().st_size,
        )
    except Exception as exc:
        set_job(job_id, status="failed", progress=0, message="Video generation failed.", error=str(exc))


@app.get("/")
def home() -> FileResponse:
    index_path = BASE_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html is missing")
    return FileResponse(index_path)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "app": "Genius Sound Command Center",
        "ffmpeg_available": bool(get_ffmpeg_exe()),
    }


@app.get("/ping")
def ping() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/upload")
def upload_test(file: UploadFile = File(...)) -> Dict[str, Any]:
    # Simple endpoint kept so old upload-button tests do not break.
    ext = safe_extension(file.filename)
    job_id = uuid.uuid4().hex
    path = UPLOAD_DIR / f"upload_{job_id}{ext}"
    save_upload(file, path)
    return {"status": "uploaded", "filename": file.filename, "size_bytes": path.stat().st_size}


@app.post("/generate")
def generate_video(audio: UploadFile = File(...), photo: UploadFile = File(...)) -> JSONResponse:
    audio_ext = safe_extension(audio.filename)
    photo_ext = safe_extension(photo.filename)

    if audio_ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported audio type '{audio_ext}'. Use MP3, WAV, M4A, AAC, FLAC, OGG, or OPUS.")
    if photo_ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported photo type '{photo_ext}'. Use JPG, JPEG, PNG, or WEBP.")

    job_id = uuid.uuid4().hex
    audio_path = UPLOAD_DIR / f"{job_id}_audio{audio_ext}"
    photo_path = UPLOAD_DIR / f"{job_id}_photo{photo_ext}"
    output_path = OUTPUT_DIR / f"{job_id}_4k_video.mp4"

    save_upload(audio, audio_path)
    save_upload(photo, photo_path)

    with JOB_LOCK:
        JOBS[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress": 5,
            "message": "Files uploaded. Starting 4K render...",
            "created_at": time.time(),
            "updated_at": time.time(),
            "audio_filename": audio.filename,
            "photo_filename": photo.filename,
        }

    thread = threading.Thread(target=run_ffmpeg_job, args=(job_id, audio_path, photo_path, output_path), daemon=True)
    thread.start()

    return JSONResponse({"job_id": job_id, "status": "queued", "progress": 5, "message": "Files uploaded. Starting 4K render..."})


@app.get("/status/{job_id}")
def status(job_id: str) -> Dict[str, Any]:
    return get_job(job_id)


@app.get("/download/{job_id}")
def download(job_id: str) -> FileResponse:
    job = get_job(job_id)
    if job.get("status") != "finished":
        raise HTTPException(status_code=400, detail="Video is not finished yet")
    filename = job.get("output_filename")
    if not filename:
        raise HTTPException(status_code=404, detail="Output filename missing")
    output_path = OUTPUT_DIR / filename
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found. It may have expired or the server restarted.")
    return FileResponse(path=output_path, filename="genius-sound-4k-video.mp4", media_type="video/mp4")


@app.get("/robots.txt")
def robots() -> PlainTextResponse:
    return PlainTextResponse("User-agent: *\nAllow: /\n")
