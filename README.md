# Render FastAPI fixed upload

Upload these files to the root of your GitHub repo, then redeploy on Render.

Render settings:

Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Test after deploy:

- `/` should return JSON status
- `/health` should return `{ "status": "healthy" }`
- `/docs` opens FastAPI docs
- `/test` opens a simple browser upload test page

Important: keep `main.py`, `requirements.txt`, and `render.yaml` in the repo root, not inside an extra folder.
