# Genius Sound Video Backend — 480p Added

This version supports:
- 480p
- 1080p
- 4K

Use 480p first to test on the small 512MB server.

DigitalOcean Run Command:
```bash
uvicorn main:app --host 0.0.0.0 --port 8080
```

Test after deploy:
```txt
/health
```

You should see:
```json
"ffmpeg": true
```
