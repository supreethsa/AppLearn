# app.py
import json
import os
import secrets
import sqlite3
import traceback
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "applearn.db")

app = Flask(__name__, static_folder='.', static_url_path='')
app.secret_key = os.environ.get("APP_SECRET_KEY", "dev-secret-change-me")

# -----------------------------
# DB helpers
# -----------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Ensure this runs once at startup
def ensure_video_views_table(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS video_views (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        video_id TEXT NOT NULL,
        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        seconds_watched REAL DEFAULT 0,
        duration REAL DEFAULT 0,
        last_position REAL DEFAULT 0,
        completed INTEGER DEFAULT 0,
        view_count INTEGER NOT NULL DEFAULT 0,
        last_session_id TEXT NOT NULL DEFAULT '',
        UNIQUE (user_id, video_id)
    );
    """)
    conn.commit()
    cols = set(table_info(conn, "video_views"))
    cur = conn.cursor()
    if "view_count" not in cols:
        cur.execute("ALTER TABLE video_views ADD COLUMN view_count INTEGER NOT NULL DEFAULT 0")
    if "last_session_id" not in cols:
        cur.execute("ALTER TABLE video_views ADD COLUMN last_session_id TEXT NOT NULL DEFAULT ''")
    conn.commit()

def ensure_game_attempts_table(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS game_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        game_id TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        last_attempt DATETIME DEFAULT CURRENT_TIMESTAMP,
        completions INTEGER NOT NULL DEFAULT 0,
        last_completed DATETIME,
        UNIQUE (user_id, game_id)
    );
    """)
    conn.commit()
    cols = set(table_info(conn, "game_attempts"))
    cur = conn.cursor()
    if "completions" not in cols:
        cur.execute("ALTER TABLE game_attempts ADD COLUMN completions INTEGER NOT NULL DEFAULT 0")
    if "last_completed" not in cols:
        cur.execute("ALTER TABLE game_attempts ADD COLUMN last_completed DATETIME")
    conn.commit()


def ensure_game_sessions_table(conn):
    conn.execute("""
    CREATE TABLE IF NOT EXISTS game_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        game_id TEXT NOT NULL,
        token TEXT NOT NULL UNIQUE,
        status TEXT NOT NULL DEFAULT 'started',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        completed_at DATETIME,
        metadata TEXT,
        result_payload TEXT
    );
    """)
    conn.commit()
    cols = set(table_info(conn, "game_sessions"))
    cur = conn.cursor()
    if "metadata" not in cols:
        cur.execute("ALTER TABLE game_sessions ADD COLUMN metadata TEXT")
    if "result_payload" not in cols:
        cur.execute("ALTER TABLE game_sessions ADD COLUMN result_payload TEXT")
    if "completed_at" not in cols:
        cur.execute("ALTER TABLE game_sessions ADD COLUMN completed_at DATETIME")
    if "status" not in cols:
        cur.execute("ALTER TABLE game_sessions ADD COLUMN status TEXT NOT NULL DEFAULT 'started'")
    conn.commit()


def table_info(conn, table):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in cur.fetchall()]

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            first_name TEXT NOT NULL DEFAULT '',
            last_name  TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'student',
            school TEXT NOT NULL DEFAULT '',
            email_verified INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.commit()
    conn.close()

def migrate_db():
    """
    Ensure 'users' has the expected columns. If the table exists with an older schema,
    we incrementally ADD COLUMNs with safe defaults (so NOT NULL is satisfied).
    """
    expected = {
        "id", "email", "password_hash",
        "first_name", "last_name", "role", "school",
        "email_verified", "created_at"
    }
    conn = get_db()
    try:
        cols = set(table_info(conn, "users"))
    except sqlite3.OperationalError:
        cols = set()
    cur = conn.cursor()

    if not cols:
        # No users table yet
        init_db()
        conn.close()
        return

    missing = expected - cols
    if missing:
        # add columns one by one with compatible defaults
        if "first_name" in missing:
            cur.execute("ALTER TABLE users ADD COLUMN first_name TEXT NOT NULL DEFAULT ''")
        if "last_name" in missing:
            cur.execute("ALTER TABLE users ADD COLUMN last_name TEXT NOT NULL DEFAULT ''")
        if "role" in missing:
            cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'")
        if "school" in missing:
            cur.execute("ALTER TABLE users ADD COLUMN school TEXT NOT NULL DEFAULT ''")
        if "email_verified" in missing:
            cur.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")
        if "created_at" in missing:
            cur.execute("ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT ''")
        conn.commit()
    conn.close()

# Initialize / migrate on boot
init_db()
migrate_db()
_conn = get_db()
try:
    ensure_video_views_table(_conn)
    ensure_game_attempts_table(_conn)
    ensure_game_sessions_table(_conn)
finally:
    _conn.close()

# -----------------------------
# Helpers
# -----------------------------
def sanitize_email(e):
    return (e or "").strip().lower()

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email, first_name, last_name, role, school, email_verified FROM users WHERE id = ?",
        (uid,),
    )
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

# -----------------------------
# API: Auth
# -----------------------------
@app.route("/api/signup", methods=["POST"])
def api_signup():
    try:
        data = request.get_json(force=True, silent=True) or {}
        first = (data.get("first_name") or "").strip()
        last  = (data.get("last_name") or "").strip()
        email = sanitize_email(data.get("email"))
        role  = (data.get("role") or "").strip().lower()
        school = (data.get("school") or "").strip()
        pw    = data.get("password") or ""
        if role not in {"student", "teacher"}:
            return jsonify(ok=False, error="Please select student or teacher."), 400
        if not (first and last and email and pw):
            return jsonify(ok=False, error="Missing required fields"), 400

        pw_hash = generate_password_hash(pw)
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (email, password_hash, first_name, last_name, role, school, email_verified, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """, (email, pw_hash, first, last, role, school, datetime.utcnow().isoformat()+"Z"))
        conn.commit()
        conn.close()
        return jsonify(ok=True, message="Account created. You can log in now.")
    except sqlite3.IntegrityError:
        return jsonify(ok=False, error="Email already in use"), 409
    except Exception as e:
        app.logger.error("Signup error: %s\n%s", e, traceback.format_exc())
        return jsonify(ok=False, error=f"Server error: {str(e)}"), 500

@app.route("/api/login", methods=["POST"])
def api_login():
    try:
        data = request.get_json(force=True, silent=True) or {}
        email = sanitize_email(data.get("email"))
        pw    = data.get("password") or ""

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash, first_name, email_verified FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        conn.close()
        if not row or not check_password_hash(row["password_hash"], pw):
            return jsonify(ok=False, error="Invalid email or password"), 401
        if not row["email_verified"]:
            return jsonify(ok=False, error="Email not verified"), 403

        session["user_id"] = row["id"]
        return jsonify(ok=True)
    except Exception as e:
        app.logger.error("Login error: %s\n%s", e, traceback.format_exc())
        return jsonify(ok=False, error=f"Server error: {str(e)}"), 500

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify(ok=True)

@app.route("/api/me", methods=["GET"])
def api_me():
    u = current_user()
    if not u:
        return jsonify(authenticated=False)
    return jsonify(
        authenticated=True,
        first_name=u["first_name"],
        email=u["email"],
        role=u.get("role"),
        school=u.get("school"),
    )

# -----------------------------
# Static fallback
# -----------------------------
@app.route("/", methods=["GET"])
def root():
    base_dir = os.path.dirname(os.path.abspath(__file__))  # folder with app.py
    for candidate in ("Home.html", "Index.html"):          # Home first
        fp = os.path.join(base_dir, candidate)
        if os.path.exists(fp):
            return send_from_directory(base_dir, candidate)
    return "Home.html not found", 404

@app.route("/<path:path>", methods=["GET"])
def static_proxy(path):
    static_path = os.path.join(app.static_folder, path)
    if os.path.exists(static_path):
        return send_from_directory(app.static_folder, path)
    return jsonify(ok=False, error="Not found"), 404

# -----------------------------
# API: Video progress
# -----------------------------
def require_user():
    user = current_user()
    if not user:
        return None, (jsonify(ok=False, error="Authentication required"), 401)
    return user, None

def parse_json_request():
    data = request.get_json(silent=True)
    if data is not None:
        return data
    try:
        raw = request.get_data(as_text=True)
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def record_game_attempt(user_id, game_id, attempts_delta=0, completions_delta=0, conn=None):
    try:
        attempts_delta = int(attempts_delta or 0)
    except (TypeError, ValueError):
        attempts_delta = 0
    try:
        completions_delta = int(completions_delta or 0)
    except (TypeError, ValueError):
        completions_delta = 0

    attempts_delta = max(0, attempts_delta)
    completions_delta = max(0, completions_delta)

    if attempts_delta <= 0 and completions_delta <= 0:
        return

    local_conn = conn or get_db()
    close_conn = conn is None

    try:
        cur = local_conn.cursor()
        cur.execute(
            """
            INSERT INTO game_attempts (user_id, game_id, attempts, last_attempt, completions, last_completed)
            VALUES (?, ?, ?, CASE WHEN ? > 0 THEN CURRENT_TIMESTAMP ELSE NULL END,
                    ?, CASE WHEN ? > 0 THEN CURRENT_TIMESTAMP ELSE NULL END)
            ON CONFLICT(user_id, game_id)
            DO UPDATE SET
                attempts = game_attempts.attempts + excluded.attempts,
                completions = game_attempts.completions + excluded.completions,
                last_attempt = CASE
                    WHEN excluded.last_attempt IS NOT NULL THEN excluded.last_attempt
                    ELSE game_attempts.last_attempt
                END,
                last_completed = CASE
                    WHEN excluded.last_completed IS NOT NULL THEN excluded.last_completed
                    ELSE game_attempts.last_completed
                END
            """,
            (
                user_id,
                game_id,
                attempts_delta,
                attempts_delta,
                completions_delta,
                completions_delta,
            ),
        )
        if close_conn:
            local_conn.commit()
    finally:
        if close_conn:
            local_conn.close()

@app.route("/api/video/progress", methods=["GET", "POST"])
def api_video_progress():
    user, error = require_user()
    if error:
        return error

    conn = get_db()
    cur = conn.cursor()

    if request.method == "GET":
        ids_param = request.args.get("ids")
        requested = None
        if ids_param:
            requested = [vid for vid in ids_param.split(",") if vid]
        else:
            requested = request.args.getlist("video_id") or None

        try:
            if requested:
                placeholders = ",".join("?" for _ in requested)
                cur.execute(
                    f"""
                    SELECT video_id, seconds_watched, duration, last_position, completed, view_count
                    FROM video_views
                    WHERE user_id = ? AND video_id IN ({placeholders})
                    """,
                    (user["id"], *requested),
                )
            else:
                cur.execute(
                    """
                    SELECT video_id, seconds_watched, duration, last_position, completed, view_count
                    FROM video_views
                    WHERE user_id = ?
                    """,
                    (user["id"],),
                )
            rows = cur.fetchall()
        finally:
            conn.close()

        views = {}
        for row in rows:
            duration = float(row["duration"] or 0)
            seconds = float(row["seconds_watched"] or 0)
            progress = min(1.0, seconds / duration) if duration > 0 else 0.0
            views[row["video_id"]] = {
                "video_id": row["video_id"],
                "seconds_watched": seconds,
                "duration": duration,
                "progress": progress,
                "last_position": float(row["last_position"] or 0),
                "completed": bool(row["completed"]) or progress >= 0.9,
                "view_count": int(row["view_count"] or 0),
            }
        return jsonify(ok=True, views=views)

    data = parse_json_request()
    video_id = (data.get("video_id") or "").strip()
    if not video_id:
        conn.close()
        return jsonify(ok=False, error="Missing video_id"), 400

    seconds_delta = float(data.get("seconds_delta") or 0)
    seconds_delta = max(0.0, min(seconds_delta, 600.0))  # clamp to 10 minutes per event
    duration = float(data.get("duration") or 0)
    duration = 0.0 if duration < 0 else duration
    position = float(data.get("position") or 0)
    position = max(0.0, position)
    session_id = (data.get("session_id") or "").strip()
    if len(session_id) > 128:
        session_id = session_id[:128]
    mark_completed = bool(data.get("completed"))

    cur.execute(
        """
        SELECT seconds_watched, duration, completed, view_count, last_session_id
        FROM video_views
        WHERE user_id = ? AND video_id = ?
        """,
        (user["id"], video_id),
    )
    row = cur.fetchone()

    prev_seconds = float(row["seconds_watched"]) if row else 0.0
    prev_duration = float(row["duration"]) if row else 0.0
    prev_completed = bool(row["completed"]) if row else False
    prev_view_count = int(row["view_count"]) if row and row["view_count"] is not None else 0
    prev_session_id = (row["last_session_id"] or "") if row else ""

    best_duration = max(prev_duration, duration)
    if best_duration <= 0 and duration > 0:
        best_duration = duration

    total_seconds = prev_seconds + seconds_delta
    if best_duration > 0:
        total_seconds = min(total_seconds, best_duration)

    completed = mark_completed or prev_completed
    if best_duration > 0 and not completed:
        completed = (total_seconds / best_duration) >= 0.9

    increment_view = False
    if mark_completed:
        if not row:
            increment_view = True
        elif session_id:
            increment_view = session_id != prev_session_id
        else:
            increment_view = not prev_completed

    new_view_count = prev_view_count + 1 if increment_view else prev_view_count
    new_session_id = session_id if increment_view and session_id else (prev_session_id if row else "")

    if row:
        cur.execute(
            """
            UPDATE video_views
            SET last_seen_at = CURRENT_TIMESTAMP,
                seconds_watched = ?,
                duration = CASE
                    WHEN ? > COALESCE(duration, 0) THEN ?
                    ELSE duration
                END,
                last_position = ?,
                completed = ?,
                view_count = ?,
                last_session_id = ?
            WHERE user_id = ? AND video_id = ?
            """,
            (
                total_seconds,
                duration,
                duration,
                min(position, best_duration or position),
                int(completed),
                new_view_count,
                new_session_id,
                user["id"],
                video_id,
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO video_views (user_id, video_id, started_at, last_seen_at,
                                     seconds_watched, duration, last_position, completed,
                                     view_count, last_session_id)
            VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?)
            """,
            (
                user["id"],
                video_id,
                total_seconds,
                duration,
                min(position, best_duration or position),
                int(completed),
                new_view_count,
                new_session_id,
            ),
        )

    conn.commit()

    cur.execute(
        """
        SELECT video_id, seconds_watched, duration, last_position, completed, view_count
        FROM video_views
        WHERE user_id = ? AND video_id = ?
        """,
        (user["id"], video_id),
    )
    updated = cur.fetchone()
    conn.close()

    duration_val = float(updated["duration"] or 0)
    seconds_val = float(updated["seconds_watched"] or 0)
    progress = min(1.0, seconds_val / duration_val) if duration_val > 0 else 0.0

    view_payload = {
        "video_id": video_id,
        "seconds_watched": seconds_val,
        "duration": duration_val,
        "progress": progress,
        "last_position": float(updated["last_position"] or 0),
        "completed": bool(updated["completed"]) or progress >= 0.9,
        "view_count": int(updated["view_count"] or 0),
    }

    return jsonify(ok=True, view=view_payload)

@app.route("/api/game/attempts", methods=["GET", "POST"])
def api_game_attempts():
    user, error = require_user()
    if error:
        return error

    conn = get_db()
    cur = conn.cursor()

    if request.method == "GET":
        ids_param = request.args.get("ids")
        if ids_param:
            requested = [gid.strip() for gid in ids_param.split(",") if gid.strip()]
        else:
            requested = request.args.getlist("game_id") or None

        try:
            if requested:
                placeholders = ",".join("?" for _ in requested)
                cur.execute(
                    f"""
                    SELECT game_id, attempts, last_attempt, completions, last_completed
                    FROM game_attempts
                    WHERE user_id = ? AND game_id IN ({placeholders})
                    """,
                    (user["id"], *requested),
                )
            else:
                cur.execute(
                    """
                    SELECT game_id, attempts, last_attempt, completions, last_completed
                    FROM game_attempts
                    WHERE user_id = ?
                    """,
                    (user["id"],),
                )
            rows = cur.fetchall()
        finally:
            conn.close()

        games = {}
        for row in rows:
            games[row["game_id"]] = {
                "game_id": row["game_id"],
                "attempts": int(row["attempts"] or 0),
                "last_attempt": row["last_attempt"],
                "completions": int(row["completions"] or 0),
                "last_completed": row["last_completed"],
            }

        if requested:
            for gid in requested:
                games.setdefault(
                    gid,
                    {
                        "game_id": gid,
                        "attempts": 0,
                        "last_attempt": None,
                        "completions": 0,
                        "last_completed": None,
                    },
                )

        return jsonify(ok=True, games=games)

    data = parse_json_request()
    game_id = (data.get("game_id") or "").strip()
    if not game_id:
        conn.close()
        return jsonify(ok=False, error="Missing game_id"), 400

    try:
        attempts_delta = int(data.get("attempts_delta") or 1)
    except (TypeError, ValueError):
        attempts_delta = 1

    try:
        completions_delta = int(data.get("completions_delta") or 0)
    except (TypeError, ValueError):
        completions_delta = 0

    record_game_attempt(
        user_id=user["id"],
        game_id=game_id,
        attempts_delta=attempts_delta,
        completions_delta=completions_delta,
        conn=conn,
    )
    conn.commit()

    cur.execute(
        """
        SELECT attempts, last_attempt, completions, last_completed
        FROM game_attempts
        WHERE user_id = ? AND game_id = ?
        """,
        (user["id"], game_id),
    )
    row = cur.fetchone()
    conn.close()

    attempts_val = int(row["attempts"] or 0) if row else 0
    last_attempt = row["last_attempt"] if row else None
    completions_val = int(row["completions"] or 0) if row else 0
    last_completed = row["last_completed"] if row else None

    return jsonify(
        ok=True,
        game={
            "game_id": game_id,
            "attempts": attempts_val,
            "last_attempt": last_attempt,
            "completions": completions_val,
            "last_completed": last_completed,
        },
    )


@app.route("/api/game/start", methods=["POST"])
def api_game_start():
    user, error = require_user()
    if error:
        return error

    data = parse_json_request()
    game_id = (data.get("game_id") or "").strip()
    if not game_id:
        return jsonify(ok=False, error="Missing game_id"), 400

    try:
        attempts_delta = int(data.get("attempts_delta") or 1)
    except (TypeError, ValueError):
        attempts_delta = 1

    metadata = data.get("metadata")
    metadata_json = None
    if metadata is not None:
        try:
            metadata_json = json.dumps(metadata)
        except (TypeError, ValueError):
            metadata_json = json.dumps({"raw": metadata})

    conn = get_db()
    cur = conn.cursor()
    token = None
    session_id = None

    for _ in range(8):
        candidate = secrets.token_urlsafe(24)
        try:
            cur.execute(
                """
                INSERT INTO game_sessions (user_id, game_id, token, status, created_at, metadata)
                VALUES (?, ?, ?, 'started', CURRENT_TIMESTAMP, ?)
                """,
                (user["id"], game_id, candidate, metadata_json),
            )
            token = candidate
            session_id = cur.lastrowid
            break
        except sqlite3.IntegrityError:
            conn.rollback()
            token = None
            session_id = None
            continue

    if token is None:
        conn.rollback()
        conn.close()
        return jsonify(ok=False, error="Could not create game session"), 500

    record_game_attempt(
        user_id=user["id"],
        game_id=game_id,
        attempts_delta=attempts_delta,
        conn=conn,
    )

    cur.execute(
        """
        SELECT attempts, completions, last_attempt, last_completed
        FROM game_attempts
        WHERE user_id = ? AND game_id = ?
        """,
        (user["id"], game_id),
    )
    row = cur.fetchone()
    conn.commit()
    conn.close()

    attempts_val = int(row["attempts"] or 0) if row else attempts_delta
    completions_val = int(row["completions"] or 0) if row else 0

    return jsonify(
        ok=True,
        session={
            "id": session_id,
            "game_id": game_id,
            "token": token,
            "attempts": attempts_val,
            "completions": completions_val,
        },
    )


@app.route("/api/game/complete", methods=["POST"])
def api_game_complete():
    data = parse_json_request()
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify(ok=False, error="Missing token"), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, user_id, game_id, status, completed_at
        FROM game_sessions
        WHERE token = ?
        """,
        (token,),
    )
    session_row = cur.fetchone()
    if not session_row:
        conn.close()
        return jsonify(ok=False, error="Invalid or expired token"), 404

    requested_game_id = (data.get("game_id") or "").strip()
    if requested_game_id and requested_game_id != session_row["game_id"]:
        conn.close()
        return jsonify(ok=False, error="Token does not match game_id"), 400

    user = current_user()
    if user and user["id"] != session_row["user_id"]:
        conn.close()
        return jsonify(ok=False, error="Forbidden"), 403

    normalized_status = (data.get("status") or "completed").strip().lower()
    if normalized_status not in {"completed", "aborted", "failed"}:
        normalized_status = "completed"

    already_completed = bool(session_row["completed_at"])

    result_payload = None
    if "result" in data:
        result_payload = data["result"]
    elif "details" in data:
        result_payload = data["details"]
    elif "metadata" in data:
        result_payload = {"metadata": data["metadata"]}

    result_json = None
    if result_payload is not None:
        try:
            result_json = json.dumps(result_payload)
        except (TypeError, ValueError):
            result_json = json.dumps({"raw": result_payload})

    update_clauses = ["status = ?"]
    params = [normalized_status]

    if normalized_status == "completed":
        update_clauses.append("completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP)")
    elif normalized_status in {"aborted", "failed"} and not already_completed:
        update_clauses.append("completed_at = NULL")

    if result_json is not None:
        update_clauses.append("result_payload = ?")
        params.append(result_json)

    params.append(session_row["id"])
    cur.execute(
        f"UPDATE game_sessions SET {', '.join(update_clauses)} WHERE id = ?",
        params,
    )

    newly_completed = normalized_status == "completed" and not already_completed
    if newly_completed:
        record_game_attempt(
            user_id=session_row["user_id"],
            game_id=session_row["game_id"],
            completions_delta=1,
            conn=conn,
        )

    cur.execute(
        """
        SELECT game_id, status, created_at, completed_at, result_payload
        FROM game_sessions
        WHERE id = ?
        """,
        (session_row["id"],),
    )
    updated_row = cur.fetchone()
    conn.commit()
    conn.close()

    session_payload = {
        "game_id": updated_row["game_id"],
        "token": token,
        "status": updated_row["status"],
        "created_at": updated_row["created_at"],
        "completed_at": updated_row["completed_at"],
        "already_completed": already_completed,
    }

    if updated_row["result_payload"]:
        try:
            session_payload["result"] = json.loads(updated_row["result_payload"])
        except (TypeError, ValueError, json.JSONDecodeError):
            session_payload["result"] = updated_row["result_payload"]

    return jsonify(ok=True, session=session_payload)

@app.route("/api/teacher/stats", methods=["GET"])
def api_teacher_stats():
    user, error = require_user()
    if error:
        return error

    if (user.get("role") or "").lower() != "teacher":
        return jsonify(ok=False, error="Forbidden"), 403

    teacher_school = (user.get("school") or "").strip()
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, first_name, last_name
        FROM users
        WHERE role = 'student' AND school = ?
        ORDER BY last_name COLLATE NOCASE, first_name COLLATE NOCASE
        """,
        (teacher_school,),
    )
    students = cur.fetchall()

    if not students:
        conn.close()
        return jsonify(
            ok=True,
            summary={
                "total_views": 0,
                "total_attempts": 0,
                "total_completions": 0,
                "student_count": 0,
            },
            students=[],
        )

    student_ids = [row["id"] for row in students]
    placeholders = ",".join("?" for _ in student_ids)

    view_totals = {sid: 0 for sid in student_ids}
    attempt_totals = {sid: 0 for sid in student_ids}
    completion_totals = {sid: 0 for sid in student_ids}

    cur.execute(
        f"""
        SELECT user_id, SUM(view_count) AS total_views
        FROM video_views
        WHERE user_id IN ({placeholders})
        GROUP BY user_id
        """,
        student_ids,
    )
    for row in cur.fetchall():
        view_totals[row["user_id"]] = int(row["total_views"] or 0)

    cur.execute(
        f"""
        SELECT user_id, SUM(attempts) AS total_attempts, SUM(completions) AS total_completions
        FROM game_attempts
        WHERE user_id IN ({placeholders})
        GROUP BY user_id
        """,
        student_ids,
    )
    for row in cur.fetchall():
        attempt_totals[row["user_id"]] = int(row["total_attempts"] or 0)
        completion_totals[row["user_id"]] = int(row["total_completions"] or 0)

    conn.close()

    student_entries = []
    total_views_sum = 0
    total_attempts_sum = 0
    total_completions_sum = 0

    for row in students:
        sid = row["id"]
        views = view_totals.get(sid, 0)
        attempts = attempt_totals.get(sid, 0)
        completions = completion_totals.get(sid, 0)
        total_views_sum += views
        total_attempts_sum += attempts
        total_completions_sum += completions
        full_name = f"{row['first_name'] or ''} {row['last_name'] or ''}".strip()
        student_entries.append({
            "id": sid,
            "first_name": row["first_name"],
            "last_name": row["last_name"],
            "full_name": full_name,
            "total_views": views,
            "total_attempts": attempts,
            "total_completions": completions,
        })

    summary = {
        "total_views": total_views_sum,
        "total_attempts": total_attempts_sum,
        "total_completions": total_completions_sum,
        "student_count": len(student_entries),
    }

    return jsonify(ok=True, summary=summary, students=student_entries)

# -----------------------------
# API error pages -> JSON
# -----------------------------
@app.errorhandler(500)
def handle_500(err):
    if request.path.startswith("/api/"):
        # In debug, include a short hint; logs have full traceback
        return jsonify(ok=False, error="Server error"), 500
    return err

if __name__ == "__main__":
    # Set FLASK_DEBUG=1 in env if you want auto-reload & stacktraces in console.
    app.run("127.0.0.1", 5000, debug=True)
