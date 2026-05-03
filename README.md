# Genius Sound Command Center + 4K Video Generator

This package keeps the full Genius Sound Command Center app:

- Contracts
- Artists
- Pro Audio Analyzer
- Riddim Prompt
- SEO
- Projects
- Cloud/Supabase

It adds a new **Video** tab for generating a 4K MP4 from one audio file and one photo.

## Render settings

Build Command:

```bash
pip install -r requirements.txt
```

Start Command:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port $PORT
```

Using `python -m uvicorn` avoids the common Render `Exited with status 127` problem caused by Render trying to run a command it cannot find.

## Endpoints

- `/` loads the website
- `/health` tests the backend
- `/generate` starts the 4K render
- `/status/<job_id>` returns progress
- `/download/<job_id>` downloads the finished MP4
- `/docs` shows FastAPI API docs

## Notes

Generated files are stored in temporary server storage. On Render free instances, the first request after inactivity can take longer, and long 4K renders can take time.

You can set these optional Render environment variables:

```text
VIDEO_PRESET=ultrafast
VIDEO_CRF=18
```

`VIDEO_PRESET=ultrafast` renders faster. `VIDEO_CRF=18` is high quality; higher CRF creates smaller files.
