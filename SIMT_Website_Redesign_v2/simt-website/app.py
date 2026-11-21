"""
SIMT full-stack consultancy website.
FastAPI serves responsive Jinja pages and handles real inquiry storage and
optional SMTP alerts. No customer message is silently discarded.
"""
from __future__ import annotations

import hmac
import hashlib
import os
import re
import secrets
import smtplib
import sqlite3
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import urlparse, quote

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from content import PROJECTS, SERVICES, AUDIENCES, STEPS

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DATABASE_PATH", str(ROOT / "data" / "simt.sqlite3")))
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_VERCEL = os.getenv("VERCEL", "").lower() in ("1", "true")
SIMT_EMAIL = os.getenv("SIMT_EMAIL", "simt.consultancy007@gmail.com").strip()
# SIMT supplied this number for its website contact link. The WhatsApp Business
# profile/automated greeting still needs to be activated by the team.
WHATSAPP_NUMBER = re.sub(r"\D", "", os.getenv("WHATSAPP_NUMBER", "923104405529"))
CALENDLY_URL = os.getenv("CALENDLY_URL", "https://calendly.com/simt-consultancy007/30min").strip()
LINKEDIN_URL = "https://www.linkedin.com/company/simt-marketing"
TEAM_MEMBERS = [
    {
        "name": "Mazahir Ali",
        "role": "Digital & Social Strategist",
        "bio": "Driving purposeful digital communication through strategic social media direction, online positioning and audience engagement.",
        "email": "mazahir@simt.com",
        "initials": "MA",
    },
    {
        "name": "Umm-E-Abeeha",
        "role": "Branding & Client Relations",
        "bio": "Shaping distinctive brand identities and meaningful client relationships through consistent communication and thoughtful brand positioning.",
        "email": "abeeha@simt.com",
        "initials": "UA",
    },
    {
        "name": "Muhammad Mohsin Umar",
        "role": "Research & Location Analyst",
        "bio": "Bringing market intelligence and location-focused research into business decisions, helping identify opportunities through informed analysis.",
        "email": "mmohsin@simt.com",
        "initials": "MM",
    },
    {
        "name": "Aneesa Riaz",
        "role": "Marketing Strategy Lead",
        "bio": "Translating business objectives into focused marketing direction through strategic planning, market understanding and purposeful execution.",
        "email": "aneesa@simt.com",
        "initials": "AR",
    },
]
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "").strip()
SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() != "false"
CALENDLY_WEBHOOK_SIGNING_KEY = os.getenv("CALENDLY_WEBHOOK_SIGNING_KEY", "").strip()
app = FastAPI(title="SIMT | Direction That Drives Growth", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))
templates.env.autoescape = True
_lock = threading.RLock()
_rate: dict[str, deque[float]] = defaultdict(deque)
_salt = "simt-admin"
_signer = URLSafeTimedSerializer(SESSION_SECRET, salt=_salt) if SESSION_SECRET else None

class PostgresCompatConnection:
    """Small adapter so existing qmark SQL works with psycopg 3 and dict rows."""
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        ignore_insert = bool(re.match(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO", sql, re.I))
        sql = re.sub(r"^\s*INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", sql, flags=re.I)
        sql = sql.replace("?", "%s")
        sql = re.sub(r"(?<!:):([A-Za-z_][A-Za-z0-9_]*)", r"%(\1)s", sql)
        if ignore_insert:
            sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        return self.connection.execute(sql, params)

    def commit(self):
        self.connection.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.connection.rollback()
            else:
                self.connection.commit()
        finally:
            self.connection.close()


def db():
    if DATABASE_URL:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("DATABASE_URL is set but psycopg is not installed.") from exc
        connection = psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=8)
        return PostgresCompatConnection(connection)
    if IS_VERCEL:
        raise HTTPException(status_code=503, detail="Persistent database is not configured. Set DATABASE_URL to a managed PostgreSQL connection before accepting inquiries.")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    with db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS inquiries (
          id TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          name TEXT NOT NULL,
          email TEXT NOT NULL,
          company TEXT NOT NULL DEFAULT '',
          audience TEXT NOT NULL DEFAULT '',
          service TEXT NOT NULL DEFAULT '',
          message TEXT NOT NULL,
          preferred_date TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'new',
          notification_status TEXT NOT NULL DEFAULT 'pending',
          created_at TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_inquiries_created ON inquiries(created_at DESC)")
        conn.execute("""
        CREATE TABLE IF NOT EXISTS calendly_events (
          invitee_uri TEXT PRIMARY KEY,
          event_uri TEXT NOT NULL DEFAULT '',
          event_name TEXT NOT NULL DEFAULT '',
          invitee_name TEXT NOT NULL DEFAULT '',
          invitee_email TEXT NOT NULL DEFAULT '',
          start_time TEXT NOT NULL DEFAULT '',
          end_time TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'scheduled',
          updated_at TEXT NOT NULL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_calendly_events_updated ON calendly_events(updated_at DESC)")
        conn.commit()

try:
    init_db()
except HTTPException as exc:
    if not (IS_VERCEL and exc.status_code == 503):
        raise

def site_context(request: Request, **kwargs):
    return {
        "request": request,
        "site_email": SIMT_EMAIL,
        "whatsapp": f"https://wa.me/{WHATSAPP_NUMBER}?text={quote('Hello SIMT Team! I visited your website and would like to learn more about your marketing consultancy services.', safe='')}" if WHATSAPP_NUMBER else None,
        "calendly": CALENDLY_URL if CALENDLY_URL.startswith("https://calendly.com/") else None,
        "linkedin": LINKEDIN_URL,
        "team_members": TEAM_MEMBERS,
        "services": SERVICES,
        "audiences": AUDIENCES,
        "steps": STEPS,
        "projects": PROJECTS,
        "year": datetime.now(timezone.utc).year,
        **kwargs
    }

def page(request, template, title, description, **kwargs):
    return templates.TemplateResponse(
        request=request, name=template,
        context=site_context(request, page_title=title, page_description=description, **kwargs)
    )

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return page(request, "home.html", "Strategic Marketing & Market-Entry Consultancy", "SIMT guides founders and businesses with customer insights, market-entry feasibility and practical marketing strategy.", active="home")

@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    return page(request, "about.html", "About SIMT", "Meet SIMT's perspective, mission and four complementary consultancy roles.", active="about")

@app.get("/services", response_class=HTMLResponse)
def services_page(request: Request):
    return page(request, "services.html", "Services", "Explore SIMT's eight marketing, market-entry and business strategy services.", active="services")

@app.get("/who-we-help", response_class=HTMLResponse)
def who(request: Request):
    return page(request, "who.html", "Who We Help", "Dedicated strategic consultancy support for startups, SMEs and large companies.", active="who")

@app.get("/approach", response_class=HTMLResponse)
def approach(request: Request):
    return page(request, "approach.html", "Our Approach", "Discover how SIMT moves from understanding a question to making a practical recommendation.", active="approach")

@app.get("/concept-projects", response_class=HTMLResponse)
def concept(request: Request):
    return page(request, "projects.html", "Concept Projects", "Four illustrative studies showing how SIMT might research and plan for different business challenges.", active="projects")

@app.get("/concept-projects/{slug}", response_class=HTMLResponse)
def project(request: Request, slug: str):
    project_data = next((p for p in PROJECTS if p["slug"] == slug), None)
    if not project_data:
        raise HTTPException(404, "Concept project not found")
    return page(request, "project_detail.html", project_data["title"], project_data["summary"], active="projects", project=project_data)

@app.get("/contact", response_class=HTMLResponse)
def contact(request: Request):
    return page(request, "contact.html", "Contact & Consultation", "Send SIMT a business inquiry or request a consultation, with optional WhatsApp and Calendly connections.", active="contact")

@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return page(request, "privacy.html", "Privacy Notice", "Learn about the personal information SIMT collects through its inquiry and consultation forms.", active="privacy")

def rate_limit(key: str, n: int, seconds: int) -> bool:
    now = time.monotonic()
    with _lock:
        q = _rate[key]
        while q and now - q[0] > seconds:
            q.popleft()
        if len(q) >= n:
            return False
        q.append(now)
        return True

def origin_valid(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True  # non-browser clients need not send an Origin
    parsed = urlparse(origin)
    return parsed.scheme in ("http", "https") and parsed.netloc == request.headers.get("host")

def notify_inbox(record: dict) -> str:
    if not (SMTP_HOST and SMTP_FROM):
        return "not_configured"
    msg = EmailMessage()
    msg["Subject"] = f"[SIMT] {record['kind'].title()} — {record['name']} ({record['id']})"
    msg["From"] = SMTP_FROM
    msg["To"] = SIMT_EMAIL
    # Reply-To verified only by form validation, not authenticated;
    # avoid using it to prevent sender-spoofing assumptions.
    msg.set_content(
        f"New SIMT {record['kind']} — {record['id']}\n\n"
        f"Name: {record['name']}\nEmail: {record['email']}\n"
        f"Company: {record['company']}\nAudience: {record['audience']}\n"
        f"Service: {record['service']}\nPreferred date: {record['preferred_date']}\n\n"
        f"Message:\n{record['message']}\n\n"
        "Review this inquiry in the protected SIMT admin dashboard."
    )
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=9) as server:
            if SMTP_STARTTLS:
                server.starttls()
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        return "sent"
    except Exception:
        # The inquiry remains stored. Do not disclose SMTP credentials to visitors.
        return "failed"



def _format_booking_time(value: str, timezone_name: str = "") -> str:
    if not value:
        return "To be confirmed"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timezone_name:
            try:
                dt = dt.astimezone(ZoneInfo(timezone_name))
            except ZoneInfoNotFoundError:
                pass
        return dt.strftime("%A, %d %B %Y · %I:%M %p")
    except (ValueError, TypeError):
        return value


def send_invitee_booking_email(event_type: str, booking: dict) -> str:
    """Send a SIMT-branded transactional email to the Calendly invitee."""
    recipient = booking.get("invitee_email", "").strip()
    if not recipient or not (SMTP_HOST and SMTP_FROM):
        return "not_configured"
    created = event_type == "invitee.created"
    first_name = (booking.get("invitee_name") or "there").strip().split()[0]
    subject = (
        "Your SIMT Strategy Consultation is confirmed"
        if created else "Your SIMT Strategy Consultation has been canceled"
    )
    start = _format_booking_time(booking.get("start_time", ""), booking.get("timezone", ""))
    end = _format_booking_time(booking.get("end_time", ""), booking.get("timezone", ""))
    timezone_name = booking.get("timezone", "") or "your local timezone"
    event_name = booking.get("event_name") or "SIMT Strategy Consultation"
    questions = booking.get("questions_and_answers") or []
    notes = []
    for item in questions:
        if isinstance(item, dict):
            question = str(item.get("question", "")).strip()
            answer = str(item.get("answer", "")).strip()
            if answer:
                notes.append(f"{question}: {answer}" if question else answer)
    notes_text = "\n".join(notes) if notes else "No additional preparation notes were provided."
    if created:
        headline = "Your conversation is on the calendar."
        intro = "Thank you for booking a session with SIMT. We look forward to learning about your business and the decisions ahead."
        action = "Please keep this email for your reference. If your plans change, use the reschedule or cancellation links in the original Calendly invitation."
    else:
        headline = "Your consultation booking has been canceled."
        intro = "This email confirms that your SIMT consultation booking has been canceled."
        action = "If you would like to choose another time, you can book a new session using the consultation link on our website."
    plain = (
        f"Hello {first_name},\n\n{headline}\n\n{intro}\n\n"
        f"SESSION DETAILS\n{event_name}\nStart: {start}\nEnd: {end}\nTimezone: {timezone_name}\n\n"
        f"WHAT YOU SHARED\n{notes_text}\n\n{action}\n\n"
        "Warm regards,\nSIMT Strategy Team\n"
        "Direction That Drives Growth\n"
        f"{SIMT_EMAIL}\n"
    )
    safe = lambda value: (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))
    notes_html = "<br>".join(safe(line) for line in notes) if notes else "No additional preparation notes were provided."
    status_label = "BOOKING CONFIRMED" if created else "BOOKING CANCELED"
    html = f"""<!doctype html><html><body style="margin:0;background:#f5f2ed;font-family:Arial,sans-serif;color:#292824">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f5f2ed;padding:32px 12px"><tr><td align="center">
<table role="presentation" width="600" cellspacing="0" cellpadding="0" style="max-width:600px;width:100%;background:#fffdfa">
<tr><td style="padding:30px 38px 24px;border-bottom:1px solid #e9e1d8">
<div style="font-family:Georgia,serif;font-size:28px;letter-spacing:4px;color:#a85f3d">SIMT</div>
<div style="font-size:10px;letter-spacing:2px;color:#82776e;margin-top:6px">DIRECTION THAT DRIVES GROWTH</div></td></tr>
<tr><td style="padding:36px 38px 12px"><div style="font-size:10px;letter-spacing:2px;color:#a85f3d;font-weight:bold">{status_label}</div>
<h1 style="font-family:Georgia,serif;font-size:30px;font-weight:normal;line-height:1.2;margin:14px 0">{safe(headline)}</h1>
<p style="font-size:15px;line-height:1.7;color:#615b55">Hello {safe(first_name)},<br>{safe(intro)}</p></td></tr>
<tr><td style="padding:12px 38px 26px"><div style="background:#f7f3ee;border-left:3px solid #b66c49;padding:20px 22px">
<div style="font-size:10px;letter-spacing:1.6px;color:#a85f3d;font-weight:bold;margin-bottom:12px">YOUR SESSION</div>
<div style="font-family:Georgia,serif;font-size:20px;margin-bottom:12px">{safe(event_name)}</div>
<div style="font-size:14px;line-height:1.8;color:#514c46"><b>Start:</b> {safe(start)}<br><b>End:</b> {safe(end)}<br><b>Timezone:</b> {safe(timezone_name)}</div>
</div></td></tr>
<tr><td style="padding:0 38px 24px"><div style="font-size:10px;letter-spacing:1.6px;color:#a85f3d;font-weight:bold;margin-bottom:10px">YOUR PREPARATION NOTES</div>
<p style="font-size:14px;line-height:1.7;color:#615b55">{notes_html}</p>
<p style="font-size:14px;line-height:1.7;color:#615b55">{safe(action)}</p></td></tr>
<tr><td style="padding:22px 38px;background:#292824;color:#f8f4ef">
<div style="font-family:Georgia,serif;font-size:20px">A clearer direction starts with a conversation.</div>
<div style="font-size:12px;color:#d7c9bd;line-height:1.8;margin-top:10px">Warm regards,<br><b style="color:#fff">SIMT Strategy Team</b><br>{safe(SIMT_EMAIL)}</div></td></tr>
</table></td></tr></table></body></html>"""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = recipient
    msg["Reply-To"] = SIMT_EMAIL
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=9) as server:
            if SMTP_STARTTLS:
                server.starttls()
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        return "sent"
    except Exception:
        return "failed"


def verify_calendly_signature(raw_body: bytes, signature_header: str, secret: str, now: int | None = None) -> bool:
    """Validate Calendly's timestamped HMAC-SHA256 signature (180-second replay window)."""
    if not secret or not signature_header:
        return False
    parts = {}
    for item in signature_header.split(","):
        if "=" in item:
            key, value = item.strip().split("=", 1)
            parts[key] = value
    timestamp = parts.get("t", "")
    supplied = parts.get("v1", "")
    if not timestamp.isdigit() or not re.fullmatch(r"[a-fA-F0-9]{64}", supplied):
        return False
    current = int(time.time()) if now is None else int(now)
    if abs(current - int(timestamp)) > 180:
        return False
    signed = timestamp.encode("ascii") + b"." + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied.lower())


def notify_calendly_activity(event_type: str, booking: dict) -> str:
    """Send an internal SIMT alert. Calendly remains responsible for invitee confirmations."""
    if not (SMTP_HOST and SMTP_FROM):
        return "not_configured"
    action = "New booking" if event_type == "invitee.created" else "Booking canceled"
    msg = EmailMessage()
    msg["Subject"] = f"[SIMT] {action}: {booking.get('invitee_name') or 'Invitee'}"
    msg["From"] = SMTP_FROM
    msg["To"] = SIMT_EMAIL
    msg.set_content(
        f"{action} received from Calendly.\\n\\n"
        f"Invitee: {booking.get('invitee_name', '')}\\n"
        f"Email: {booking.get('invitee_email', '')}\\n"
        f"Event: {booking.get('event_name', '')}\\n"
        f"Start: {booking.get('start_time', '')}\\n"
        f"End: {booking.get('end_time', '')}\\n"
        f"Status: {booking.get('status', '')}\\n"
        f"Invitee reference: {booking.get('invitee_uri', '')}\\n"
        f"Event reference: {booking.get('event_uri', '')}\\n\\n"
        "Manage this booking in Calendly. This message is an internal SIMT notification."
    )
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=9) as server:
            if SMTP_STARTTLS:
                server.starttls()
            if SMTP_USERNAME:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        return "sent"
    except Exception:
        return "failed"


@app.post("/api/webhooks/calendly")
async def calendly_webhook(request: Request):
    """Receive signed Calendly booking/cancellation events and alert the SIMT inbox."""
    if not CALENDLY_WEBHOOK_SIGNING_KEY:
        raise HTTPException(status_code=503, detail="Calendly webhook is not configured.")
    raw_body = await request.body()
    if len(raw_body) > 100_000:
        raise HTTPException(status_code=413, detail="Webhook payload is too large.")
    signature = request.headers.get("Calendly-Webhook-Signature", "")
    if not verify_calendly_signature(raw_body, signature, CALENDLY_WEBHOOK_SIGNING_KEY):
        raise HTTPException(status_code=401, detail="Invalid Calendly webhook signature.")
    try:
        body = __import__("json").loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook JSON.")
    if not isinstance(body, dict) or body.get("event") not in ("invitee.created", "invitee.canceled"):
        return {"ok": True, "ignored": True}

    payload = body.get("payload")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Missing Calendly event payload.")
    invitee_uri = payload.get("uri")
    event_data = payload.get("scheduled_event") or payload.get("event") or {}
    if isinstance(event_data, str):
        event_uri = event_data
        event_name = ""
        start_time = ""
        end_time = ""
    elif isinstance(event_data, dict):
        event_uri = event_data.get("uri", "")
        event_name = event_data.get("name", "")
        start_time = event_data.get("start_time", "")
        end_time = event_data.get("end_time", "")
    else:
        event_uri, event_name, start_time, end_time = "", "", "", ""
    if not isinstance(invitee_uri, str) or not invitee_uri.startswith("https://api.calendly.com/"):
        raise HTTPException(status_code=400, detail="Missing or invalid invitee reference.")

    event_type = body["event"]
    status = "scheduled" if event_type == "invitee.created" else "canceled"
    booking = {
        "invitee_uri": invitee_uri,
        "event_uri": event_uri if isinstance(event_uri, str) else "",
        "event_name": event_name if isinstance(event_name, str) else "",
        "invitee_name": payload.get("name", "") if isinstance(payload.get("name", ""), str) else "",
        "invitee_email": payload.get("email", "") if isinstance(payload.get("email", ""), str) else "",
        "start_time": start_time if isinstance(start_time, str) else "",
        "end_time": end_time if isinstance(end_time, str) else "",
        "status": status,
        "timezone": payload.get("timezone", "") if isinstance(payload.get("timezone", ""), str) else "",
        "questions_and_answers": payload.get("questions_and_answers", []) if isinstance(payload.get("questions_and_answers", []), list) else [],
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    should_notify = False
    with db() as conn:
        if event_type == "invitee.created":
            cursor = conn.execute("""
                INSERT OR IGNORE INTO calendly_events
                (invitee_uri,event_uri,event_name,invitee_name,invitee_email,start_time,end_time,status,updated_at)
                VALUES (:invitee_uri,:event_uri,:event_name,:invitee_name,:invitee_email,:start_time,:end_time,:status,:updated_at)
            """, booking)
            should_notify = cursor.rowcount == 1
        else:
            existing = conn.execute("SELECT invitee_uri FROM calendly_events WHERE invitee_uri=?", (invitee_uri,)).fetchone()
            if existing:
                conn.execute("UPDATE calendly_events SET status='canceled', updated_at=? WHERE invitee_uri=?",
                             (booking["updated_at"], invitee_uri))
            else:
                conn.execute("""
                    INSERT INTO calendly_events
                    (invitee_uri,event_uri,event_name,invitee_name,invitee_email,start_time,end_time,status,updated_at)
                    VALUES (:invitee_uri,:event_uri,:event_name,:invitee_name,:invitee_email,:start_time,:end_time,:status,:updated_at)
                """, booking)
            should_notify = True
        conn.commit()
    notification = notify_calendly_activity(event_type, booking) if should_notify else "duplicate"
    invitee_notification = send_invitee_booking_email(event_type, booking) if should_notify else "duplicate"
    return {
        "ok": True, "processed": True,
        "notification": notification,
        "invitee_notification": invitee_notification
    }


@app.post("/api/inquiries")
async def new_inquiry(request: Request):
    if not origin_valid(request):
        raise HTTPException(status_code=403, detail="Invalid request origin.")
    try:
        length = int(request.headers.get("content-length", "0"))
    except ValueError:
        length = 0
    if length > 14000:
        raise HTTPException(status_code=413, detail="Submission is too large.")
    ip = request.client.host if request.client else "unknown"
    if not rate_limit("inquiry:" + ip, 6, 900):
        raise HTTPException(status_code=429, detail="Too many submissions. Please try again later.")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid form submission.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid form submission.")
    if payload.get("website"):  # honeypot field
        return JSONResponse(status_code=200, content={"ok": True, "reference": "received"})
    fields = ("kind", "name", "email", "company", "audience", "service", "message", "preferred_date")
    if any(not isinstance(payload.get(f, ""), str) for f in fields):
        raise HTTPException(status_code=422, detail="Invalid field values.")
    value = {key: payload.get(key, "").strip() for key in fields}
    value["email"] = value["email"].lower()
    if value["kind"] not in ("inquiry", "consultation"):
        raise HTTPException(422, "Choose an inquiry type.")
    if not 2 <= len(value["name"]) <= 100:
        raise HTTPException(422, "Please enter your name (2–100 characters).")
    if len(value["email"]) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value["email"]):
        raise HTTPException(422, "Please enter a valid email.")
    if not 12 <= len(value["message"]) <= 3000:
        raise HTTPException(422, "Please describe your request (12–3000 characters).")
    if any(len(value[f]) > lim for f,lim in (("company",140),("audience",80),("service",120),("preferred_date",30))):
        raise HTTPException(422, "One of the fields is too long.")
    if value["kind"] == "consultation" and value["preferred_date"] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value["preferred_date"]):
        raise HTTPException(422, "Invalid preferred date.")
    value.update(id=secrets.token_hex(6).upper(), created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    with db() as conn:
        conn.execute("""INSERT INTO inquiries
          (id, kind, name, email, company, audience, service, message, preferred_date, created_at)
          VALUES (:id,:kind,:name,:email,:company,:audience,:service,:message,:preferred_date,:created_at)""", value)
        conn.commit()
    notification = notify_inbox(value)
    with db() as conn:
        conn.execute("UPDATE inquiries SET notification_status=? WHERE id=?", (notification, value["id"]))
        conn.commit()
    return JSONResponse(status_code=201, content={
        "ok": True, "reference": value["id"],
        "message": "Your request has been received. SIMT will follow up using the details provided."
    })

@app.post("/api/chat")
async def simora_chat(request: Request):
    """Context-aware, curated SIMORA guide. No external AI API or visitor-data storage."""
    if not origin_valid(request):
        raise HTTPException(status_code=403, detail="Invalid request origin.")
    ip = request.client.host if request.client else "unknown"
    if not rate_limit("chat:" + ip, 30, 300):
        raise HTTPException(status_code=429, detail="SIMORA is taking a short break. Please try again in a few minutes.")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Please send a text message.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Please send a text message.")

    message = payload.get("message", "")
    history = payload.get("history", [])
    if not isinstance(message, str) or not message.strip() or len(message) > 1000:
        raise HTTPException(status_code=422, detail="Please enter a message of up to 1,000 characters.")
    if not isinstance(history, list) or len(history) > 12:
        raise HTTPException(status_code=422, detail="Please restart the conversation and try again.")
    clean_history = []
    for item in history:
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant") or not isinstance(item.get("content"), str):
            raise HTTPException(status_code=422, detail="Invalid conversation context.")
        content = item["content"].strip()
        if content:
            clean_history.append({"role": item["role"], "content": content[:1000]})

    q = message.casefold()
    prior_user_text = " ".join(x["content"] for x in clean_history if x["role"] == "user").casefold()
    combined = f"{prior_user_text} {q}"
    last_assistant = next((x["content"].casefold() for x in reversed(clean_history) if x["role"] == "assistant"), "")

    service_catalogue = {
        "audit": "marketing audits",
        "acquisition": "customer acquisition strategy",
        "research": "market research and competitor analysis",
        "location": "business location and market-entry advice",
        "brand": "branding and positioning",
        "digital": "digital marketing and social media strategy",
        "pricing": "pricing and sales-funnel improvement",
        "launch": "business launch strategy",
    }
    selected = []
    if any(w in combined for w in ("audit", "marketing performance", "marketing not working")):
        selected.append(service_catalogue["audit"])
    if any(w in combined for w in ("customer", "customers", "sales", "acquisition", "leads", "more clients")):
        selected.append(service_catalogue["acquisition"])
    if any(w in combined for w in ("research", "market size", "competitor", "competition", "demand")):
        selected.append(service_catalogue["research"])
    if any(w in combined for w in ("location", "market entry", "new city", "new area", "feasibility", "expand")):
        selected.append(service_catalogue["location"])
    if any(w in combined for w in ("brand", "branding", "position", "identity", "differentiate")):
        selected.append(service_catalogue["brand"])
    if any(w in combined for w in ("social media", "digital", "online marketing", "instagram", "facebook", "content")):
        selected.append(service_catalogue["digital"])
    if any(w in combined for w in ("price", "pricing", "funnel", "conversion", "profit", "margin")):
        selected.append(service_catalogue["pricing"])
    if any(w in combined for w in ("launch", "start a business", "starting a business", "new business")):
        selected.append(service_catalogue["launch"])
    selected = list(dict.fromkeys(selected))

    greeting = bool(re.search(r"\b(hello|hi|salam|assalam|hey|good morning|good afternoon)\b", q))
    booking = any(w in q for w in ("book", "booking", "consult", "appointment", "calendar", "calendly"))
    contact = any(w in q for w in ("whatsapp", "contact", "email", "phone", "talk to someone", "speak to someone"))
    team = any(w in q for w in ("team", "people", "who are", "team member"))
    about = any(w in q for w in ("what is simt", "about simt", "meaning of simt", "what does simt mean"))
    service_question = any(w in q for w in ("service", "services", "offer", "help", "what do you do", "what can you do"))
    price_question = any(w in q for w in ("price", "cost", "fee", "charge", "payment", "1000", "paid"))

    if greeting:
        answer = ("Hello! I'm SIMORA, SIMT's virtual assistant. I can help you find the right strategic support. "
                  "What kind of business are you working on, and what would you like to improve?")
    elif booking:
        answer = (f"You can choose an available time for a 30-minute SIMT Strategy Consultation here: {CALENDLY_URL} "
                  "The booking page shows the current available slots and booking terms.")
    elif contact:
        answer = (f"You can reach the SIMT team at {SIMT_EMAIL}, use the Contact page, or message us on WhatsApp: "
                  f"https://wa.me/{WHATSAPP_NUMBER}. Tell us briefly what you need help with and the team can guide you.")
    elif team:
        answer = ("SIMT's four-person team is: Mazahir Ali (Digital & Social Strategist), "
                  "Umm-E-Abeeha (Branding & Client Relations), Muhammad Mohsin Umar (Research & Location Analyst), "
                  "and Aneesa Riaz (Marketing Strategy Lead).")
    elif about:
        answer = ("SIMT (سمت) is a marketing strategy and market-entry consultancy. The Urdu word سمت conveys "
                  "direction, reflected in our line: 'Direction That Drives Growth.'")
    elif price_question:
        answer = ("SIMT's 30-minute Strategy Consultation can be booked through Calendly; please check the booking page "
                  "for current terms. A tailored consultancy proposal depends on the scope of work. I can't confirm "
                  "a service price, discount or payment status here.")
    elif any(w in q for w in ("startup", "sme", "small business", "large company", "corporate", "i run", "my business")):
        focus = f" I also noted your earlier interest in {', '.join(selected[:2])}." if selected else ""
        answer = ("Thanks, that helps. SIMT works with startups, SMEs and larger companies."
                  f"{focus} What is the main challenge at the moment: attracting customers, understanding the market, "
                  "standing out from competitors, or planning an expansion?")
    elif selected:
        joined = ", ".join(selected[:3])
        answer = (f"Based on what you've described, a useful starting point may be {joined}. "
                  "To narrow this down, what type of business do you run, and what is the main outcome you want?")
    elif service_question:
        answer = ("SIMT offers marketing audits, customer acquisition strategies, market research and competitor analysis, "
                  "location and market-entry advice, branding and positioning, digital and social media strategy, "
                  "pricing and sales-funnel improvement, and business launch strategies. "
                  "Which area is most relevant to your business right now?")
    elif any(w in q for w in ("thanks", "thank you", "great", "okay", "ok")):
        answer = ("You're welcome. If you'd like, tell me a little about your business challenge and I can suggest "
                  "which SIMT service may be a good starting point.")
    elif last_assistant and any(w in last_assistant for w in ("what kind of business", "what type of business", "main challenge", "main outcome")):
        answer = ("Thank you for sharing that. The best next step is to understand the decision you're trying to make. "
                  "Are you mainly looking to attract more customers, improve your marketing, research a market, "
                  "or enter a new location?")
    else:
        answer = ("I may need a little more context to guide you accurately. Are you asking about SIMT's services, "
                  "market research, customer growth, branding, business expansion, or booking a consultation?")

    return JSONResponse({
        "ok": True, "reply": answer, "assistant": "SIMORA",
        "mode": "context-aware-guided", "context_used": bool(clean_history)
    })


def admin_enabled():
    return bool(_signer and ADMIN_PASSWORD and len(ADMIN_PASSWORD) >= 12)

def admin_authorized(request: Request):
    if not admin_enabled():
        return False
    cookie = request.cookies.get("simt_admin", "")
    try:
        return _signer.loads(cookie, max_age=60 * 60 * 8) == "authenticated"
    except (BadSignature, SignatureExpired):
        return False

@app.get("/admin/login", response_class=HTMLResponse)
def login_page(request: Request):
    return page(request, "admin_login.html", "Admin Sign In", "Restricted access.", active="admin", admin_ready=admin_enabled(), login_error="")

@app.post("/admin/login")
def login_submit(request: Request, password: str = Form(...)):
    if not origin_valid(request):
        raise HTTPException(403)
    ip = request.client.host if request.client else "unknown"
    if not rate_limit("admin:" + ip, 8, 900):
        raise HTTPException(429, "Too many login attempts.")
    if not admin_enabled() or not hmac.compare_digest(password, ADMIN_PASSWORD):
        return templates.TemplateResponse(request=request, name="admin_login.html", status_code=401,
            context=site_context(request, active="admin", page_title="Admin Sign In",
                page_description="Restricted access.", admin_ready=admin_enabled(), login_error="Invalid login or admin configuration."))
    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie("simt_admin", _signer.dumps("authenticated"), httponly=True,
                        samesite="strict", secure=request.url.scheme=="https",
                        max_age=8*60*60)
    return response

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request):
    if not admin_authorized(request):
        return RedirectResponse("/admin/login", status_code=303)
    with db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM inquiries ORDER BY created_at DESC LIMIT 300")]
        counts = {r["status"]:r["n"] for r in conn.execute("SELECT status, COUNT(*) AS n FROM inquiries GROUP BY status")}
        bookings = [dict(r) for r in conn.execute("SELECT * FROM calendly_events ORDER BY updated_at DESC LIMIT 100")]
    return page(request, "admin.html", "Inquiry Dashboard", "Protected SIMT admin", active="admin", inquiries=rows, counts=counts, bookings=bookings)

@app.post("/admin/inquiries/{item_id}/status")
def set_status(request: Request, item_id: str, status: str = Form(...)):
    if not admin_authorized(request) or not origin_valid(request):
        raise HTTPException(403, "Unauthorized.")
    if status not in ("new", "contacted", "closed"):
        raise HTTPException(422, "Invalid status.")
    with db() as conn:
        conn.execute("UPDATE inquiries SET status=? WHERE id=?", (status, item_id))
        conn.commit()
    return RedirectResponse("/admin", status_code=303)

@app.post("/admin/logout")
def logout(request: Request):
    if not admin_authorized(request) or not origin_valid(request):
        raise HTTPException(403)
    response=RedirectResponse("/", status_code=303)
    response.delete_cookie("simt_admin")
    return response

@app.get("/health")
def health():
    return {
        "ok": True,
        "service": "SIMT website",
        "database_backend": "postgresql" if DATABASE_URL else "sqlite",
        "persistent_storage_ready": bool(DATABASE_URL) if IS_VERCEL else True,
    }
