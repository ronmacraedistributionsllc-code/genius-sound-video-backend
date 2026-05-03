from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import subprocess, uuid, os

app = FastAPI()

@app.get("/")
def root():
    return {"status": "Video backend running"}

@app.post("/render-video")
async def render_video(audio: UploadFile = File(...), image: UploadFile = File(...)):
    uid = str(uuid.uuid4())
    audio_path = f"/tmp/{uid}_audio"
    image_path = f"/tmp/{uid}_image"
    output_path = f"/tmp/{uid}.mp4"

    with open(audio_path, "wb") as f:
        f.write(await audio.read())

    with open(image_path, "wb") as f:
        f.write(await image.read())

    cmd = [
        "ffmpeg","-y",
        "-loop","1","-i",image_path,
        "-i",audio_path,
        "-c:v","libx264",
        "-tune","stillimage",
        "-c:a","aac",
        "-b:a","192k",
        "-pix_fmt","yuv420p",
        "-shortest",
        "-vf","scale=3840:2160",
        output_path
    ]

    subprocess.run(cmd)

    return FileResponse(output_path, media_type="video/mp4", filename="video.mp4")
