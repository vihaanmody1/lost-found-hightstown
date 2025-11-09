# Lost & Found @ Hightstown (Flask)

A clean, functional lost-and-found website for your school community.
Features include:
- Report found items (with photo uploads)
- Browse/search approved items
- Claim request form per item
- Admin review/approve/manage items and claims
- SQLite database and local image uploads

## Quick Start

1. **Download** this project as a ZIP and extract it.
2. Create a virtual environment and install dependencies:
   ```bash
   cd lostfound
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # macOS/Linux
   pip install -r requirements.txt
   ```
3. (Optional) Set admin creds and secret:
   ```bash
   set LF_ADMIN_USER=admin
   set LF_ADMIN_PASS=change-me
   set LF_SECRET_KEY=some-long-random-string
   ```
   On macOS/Linux, use `export` instead of `set`.
4. **Run** the app:
   ```bash
   python app.py
   ```
   Visit http://127.0.0.1:5000

## Notes
- Uploaded images are saved in the `uploads/` folder.
- Public sees only **approved** items; new submissions are **pending**.
- Admin can approve, mark as claimed, or delete items; and triage claims.
- This is a starter project—add email notifications, better auth, or CSV export as needed.
