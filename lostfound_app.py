from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session, abort
from werkzeug.utils import secure_filename
import sqlite3, os, datetime

# ---------------- Configuration ----------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "lostfound.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

ADMIN_USERNAME = os.environ.get("LF_ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("LF_ADMIN_PASS", "admin123")
SECRET_KEY = os.environ.get("LF_SECRET_KEY", "dev-secret-change-me")

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB upload limit
app.secret_key = SECRET_KEY

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------------- Database Helpers ----------------
def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = get_db()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            location_found TEXT,
            date_found TEXT,
            photo_filename TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (item_id) REFERENCES items(id) ON DELETE CASCADE
        );
    """)
    con.commit()
    con.close()

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- App Initialization ----------------


# ---------------- Public Routes ----------------
@app.route("/")
def home():
    con = get_db()
    stats = con.execute("""
        SELECT
          SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END) AS approved_count,
          SUM(CASE WHEN status='claimed' THEN 1 ELSE 0 END) AS claimed_count,
          SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending_count
        FROM items;
    """).fetchone()
    con.close()
    return render_template("home.html", stats=stats)

@app.route("/submit", methods=["GET", "POST"])
def submit_item():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "").strip()
        location_found = request.form.get("location_found", "").strip()
        date_found = request.form.get("date_found", "").strip()
        file = request.files.get("photo")

        if not title:
            flash("Title is required.", "error")
            return redirect(request.url)

        photo_filename = None
        if file and file.filename:
            if allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
                filename = f"{timestamp}_{filename}"
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                photo_filename = filename
            else:
                flash("Invalid image type. Allowed: png, jpg, jpeg, gif, webp", "error")
                return redirect(request.url)

        con = get_db()
        con.execute("""
            INSERT INTO items (title, description, category, location_found, date_found, photo_filename, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """, (title, description, category, location_found, date_found, photo_filename))
        con.commit()
        con.close()
        flash("Thank you for reporting — your submission is pending review.", "success")
        return redirect(url_for("home"))
    return render_template("submit.html")

@app.route("/items")
def items():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    status = "approved"
    params = [status]
    where = ["status = ?"]
    if q:
        like = f"%{q}%"
        where.append("(title LIKE ? OR description LIKE ? OR location_found LIKE ? OR category LIKE ?)")
        params.extend([like, like, like, like])
    if category:
        where.append("category = ?")
        params.append(category)
    sql = f"SELECT * FROM items WHERE {' AND '.join(where)} ORDER BY created_at DESC"
    con = get_db()
    rows = con.execute(sql, params).fetchall()
    con.close()
    return render_template("items.html", items=rows, q=q, category=category)

@app.route("/item/<int:item_id>")
def item_detail(item_id):
    con = get_db()
    item = con.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    con.close()
    if not item or item["status"] not in ("approved", "claimed"):
        abort(404)
    return render_template("item_detail.html", item=item)

@app.route("/claim/<int:item_id>", methods=["GET", "POST"])
def claim_item(item_id):
    con = get_db()
    item = con.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if not item or item["status"] not in ("approved", "claimed"):
        con.close()
        abort(404)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()
        if not (name and email):
            flash("Name and email are required.", "error")
            return redirect(request.url)
        con.execute("""
            INSERT INTO claims (item_id, name, email, message, status)
            VALUES (?, ?, ?, ?, 'new')
        """, (item_id, name, email, message))
        con.commit()
        con.close()
        flash("Your claim was submitted. An admin will contact you soon.", "success")
        return redirect(url_for("item_detail", item_id=item_id))

    con.close()
    return render_template("claim.html", item=item)

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# ---------------- Admin Routes ----------------
def is_admin():
    return session.get("admin") is True

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin"] = True
            flash("Logged in as admin.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials.", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    flash("Logged out.", "success")
    return redirect(url_for("home"))

@app.route("/admin")
def admin_dashboard():
    if not is_admin():
        return redirect(url_for("admin_login"))
    con = get_db()
    items = con.execute("SELECT * FROM items ORDER BY created_at DESC").fetchall()
    claims = con.execute("""
        SELECT c.*, i.title as item_title
        FROM claims c
        JOIN items i ON i.id = c.item_id
        ORDER BY c.created_at DESC
    """).fetchall()
    con.close()
    return render_template("admin_dashboard.html", items=items, claims=claims)

@app.route("/admin/item/<int:item_id>/status/<string:new_status>", methods=["POST"])
def admin_item_status(item_id, new_status):
    if not is_admin():
        return redirect(url_for("admin_login"))
    if new_status not in ("pending", "approved", "claimed"):
        abort(400)
    con = get_db()
    con.execute("UPDATE items SET status = ? WHERE id = ?", (new_status, item_id))
    con.commit()
    con.close()
    flash(f"Item #{item_id} status updated to {new_status}.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/item/<int:item_id>/delete", methods=["POST"])
def admin_item_delete(item_id):
    if not is_admin():
        return redirect(url_for("admin_login"))
    con = get_db()
    row = con.execute("SELECT photo_filename FROM items WHERE id = ?", (item_id,)).fetchone()
    if row and row["photo_filename"]:
        try:
            os.remove(os.path.join(app.config["UPLOAD_FOLDER"], row["photo_filename"]))
        except OSError:
            pass
    con.execute("DELETE FROM items WHERE id = ?", (item_id,))
    con.commit()
    con.close()
    flash(f"Item #{item_id} deleted.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/claim/<int:claim_id>/status/<string:new_status>", methods=["POST"])
def admin_claim_status(claim_id, new_status):
    if not is_admin():
        return redirect(url_for("admin_login"))
    if new_status not in ("new", "approved", "denied", "archived"):
        abort(400)
    con = get_db()
    con.execute("UPDATE claims SET status = ? WHERE id = ?", (new_status, claim_id))
    con.commit()
    con.close()
    flash(f"Claim #{claim_id} status updated to {new_status}.", "success")
    return redirect(url_for("admin_dashboard"))

# ---------------- Utility ----------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

# ---------------- Footer Links -----------------
@app.route('/faq')
def faq(): 
    return render_template('faq.html')

@app.route('/instructions')
def instructions(): 
    return render_template('instructions.html')

@app.route('/contact')
def contact(): 
    return render_template('contact.html')

@app.route('/sources')
def sources(): 
    return render_template('sources.html')

@app.route('/about')
def sources(): 
    return render_template('about.html')

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)