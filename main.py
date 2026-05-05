from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import shutil, uuid, subprocess, os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.get("/")
def root():
    return {"status":"running","qualities":["480p","1080p","4k"]}

@app.get("/health")
def health():
    return {"ok":True,"ffmpeg":shutil.which("ffmpeg") is not None}

def get_res(q):
    q=q.lower()
    if q=="480p": return 854,480
    if q=="4k": return 3840,2160
    return 1920,1080

@app.post("/create-video")
async def create_video(image:UploadFile=File(...),audio:UploadFile=File(...),quality:str=Form("480p"),resolution:str=Form("480p")):
    q = resolution or quality
    w,h = get_res(q)

    img_path=f"{UPLOAD_DIR}/{uuid.uuid4()}.png"
    aud_path=f"{UPLOAD_DIR}/{uuid.uuid4()}.mp3"
    out_path=f"{OUTPUT_DIR}/{uuid.uuid4()}.mp4"

    with open(img_path,"wb") as f:
        f.write(await image.read())
    with open(aud_path,"wb") as f:
        f.write(await audio.read())

    cmd=[
        "ffmpeg","-y",
        "-loop","1","-i",img_path,
        "-i",aud_path,
        "-vf",f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
        "-c:v","libx264","-c:a","aac","-shortest",out_path
    ]

    subprocess.run(cmd)

    return {"ok":True,"download_url":"/"+out_path}
