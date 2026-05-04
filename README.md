# Genius Sound Video Backend

Upload this folder to GitHub as your backend repo.

## DigitalOcean App Platform Settings

Run Command:
```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

If you use Docker, DigitalOcean will install FFmpeg automatically from the Dockerfile.

## API

Health:
```txt
GET /
GET /health
```

Create video:
```txt
POST /create-video
Form-data:
- image: JPG/PNG/WEBP
- audio: MP3/WAV/M4A
- quality: 1080p or 4k
```
