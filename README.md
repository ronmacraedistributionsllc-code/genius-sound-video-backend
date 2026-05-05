# Genius Sound Video Backend — Album Frame Fix

This version keeps the full cover art in frame and uses a stretched/blurred background behind it.

Upload/replace these on the VPS or GitHub backend repo:
- main.py
- requirements.txt
- Dockerfile

Then restart:
systemctl restart genius-video-api

Test:
https://api.ronmacraedistributions.com/health

Version should show:
album-frame-v2
