from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

app = FastAPI(title="Render FastAPI App", version="1.0.0")

# Safe default CORS. Tighten this later if you know your frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "FastAPI is running on Render.",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/test", response_class=HTMLResponse)
def test_page():
    return """
    <!doctype html>
    <html>
      <head><title>FastAPI Upload Test</title></head>
      <body style="font-family:Arial;max-width:700px;margin:40px auto;">
        <h1>FastAPI is running ✅</h1>
        <p>Use this form to test file uploads.</p>
        <form action="/upload" enctype="multipart/form-data" method="post">
          <input name="file" type="file" />
          <button type="submit">Upload</button>
        </form>
        <p>API docs: <a href="/docs">/docs</a></p>
      </body>
    </html>
    """


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Reads the upload so we can report size. For very large files, store/stream instead.
    data = await file.read()
    return {
        "status": "uploaded",
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(data),
    }
