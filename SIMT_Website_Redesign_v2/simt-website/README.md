# SIMT — Independent Full-Stack Consultancy Website

A responsive full-stack site built to match SIMT's shared Emergent design references. It is **not** a copy of Emergent's source code. All content, logic and styling in this project can be edited without Emergent credits.

## Included

- Responsive pages: Home, About, Services, Who We Help, Our Approach, Concept Projects and **four detailed concept studies**, Contact, Privacy Notice.
- Original SIMT logo mark with the outer white canvas made transparent (the original mark artwork and internal white path are preserved), plus the full original logo asset.
- Business inquiry form and **consultation-request** form (a request, **not** a confirmed appointment).
- Real FastAPI POST `/api/inquiries`: validates inputs, basic rate limiting + hidden honeypot, stores submissions in SQLite, returns a receipt reference.
- Optional SMTP notifications to `simt.consultancy007@gmail.com`.
- Password-protected admin dashboard at `/admin` to view submissions and mark as New / Contacted / Closed.
- SIMT LinkedIn company page linked in the site footer.
- About page includes the four supplied team names, with roles and biographies clearly marked for later completion.
- WhatsApp button appears when the actual number is configured.
- Calendly 30-minute booking calendar embedded on Contact, using SIMT's supplied booking link; the URL can be changed through `CALENDLY_URL`.
- Responsive desktop/tablet/mobile layouts, sticky translucent navigation, keyboard-friendly interactions, staggered reveal motion, subtle hero/logo motion, scroll progress and reduced-motion support.
- No fake testimonial, client result, office address, WhatsApp number or booked appointment.

## Run on your computer

You need Python 3.10+ and a terminal:

```bash
cd SIMT_Fullstack_Website
python -m venv .venv
# macOS/Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

Open **http://127.0.0.1:8000/**.

Use Control+C to stop it. The web server must stay running for the form to work.

## Admin dashboard

Use a separate terminal or hosting provider's Environment Variables section:

```bash
export ADMIN_PASSWORD='choose-a-unique-long-password-at-least-12-characters'
export SESSION_SECRET='choose-a-different-long-random-string'
uvicorn app:app --reload
```

For Windows PowerShell replace `export` with `$env:ADMIN_PASSWORD="..."`, etc.

Then visit **http://127.0.0.1:8000/admin**. Admin is **disabled by default** until BOTH credentials are supplied. Do not send these passwords to anyone or store them in JavaScript. The admin cookie is HttpOnly, SameSite=Strict and gets Secure on HTTPS requests.

## Inquiry notification email

The submission form **already works** locally: it validates and saves incoming inquiries into the SQLite database. In the admin dashboard you can see each one. Email delivery requires real SMTP credentials. Configure environment variables:

```bash
export SMTP_HOST='smtp.gmail.com'
export SMTP_PORT='587'
export SMTP_USERNAME='simt.consultancy007@gmail.com'
export SMTP_PASSWORD='your-email-provider-app-password-not-your-normal-password'
export SMTP_FROM='simt.consultancy007@gmail.com'
export SIMT_EMAIL='simt.consultancy007@gmail.com'
```

If using Gmail SMTP, check the current account requirements for app passwords (often requires two-step verification); support varies by account type. You may instead use a transactional mail provider and its SMTP settings. **Never** expose credentials in browser code, chat or GitHub.

If SMTP is not configured or fails, the inquiry remains saved with its notification status visible to administrators. The public form does **not** claim an email was delivered. Back up the database regularly.

## LinkedIn

The SIMT LinkedIn company page is linked in the site footer: `https://www.linkedin.com/company/simt-marketing`.

## WhatsApp (later)

Set `WHATSAPP_NUMBER` to your real international number **without the plus sign**, e.g. `92...`. The Contact link then appears automatically on all pages. Do not use the fake WhatsApp number in the reference PDF.

## Calendly

The Contact page now embeds SIMT's supplied 30-minute booking calendar: `https://calendly.com/simt-consultancy007/30min`. Visitors can select an available slot directly in the page, or open Calendly in a new tab. To change the event later, set `CALENDLY_URL` to the new real Calendly event URL.

## Team profiles and tutorial video

The About page now names the four team members supplied so far. Replace the pending role and biography text in `app.py` (`TEAM_MEMBERS`) when the team details are ready. No team photos have been fabricated.

The website's existing responsive layout already adapts to phone and desktop screens. The AI tutorial video itself still needs to be produced and supplied; no video file was included with the project upload, so this update does not pretend a finished tutorial exists.

## Deployment notes

1. Use a Python-capable web host supporting a long-running FastAPI process (or Docker container).
2. Configure HTTPS, secure environment variables and persistent storage for the SQLite database, or adapt it to a managed DB. A host with **ephemeral storage** may erase submitted leads between deploys or restarts — do not deploy SQLite there without a persistent volume.
3. Configure SMTP and test an inquiry from a different email account; verify arrival in SIMT's inbox and visibility in `/admin`.
4. Set a strong `ADMIN_PASSWORD` and independent `SESSION_SECRET` before public launch.
5. Configure WhatsApp, Calendly and a custom domain when ready. Prices and free-tier restrictions depend on hosting and vendors.
6. Consider stronger production controls for a public high-traffic site: managed Postgres, captcha/anti-bot service, automated database backups, admin multi-factor auth, request logging that excludes PII, and uptime monitoring.
7. Review the draft privacy notice for applicable legal requirements, actual data retention practices, host and email service before launch.
8. Images `home-consultancy.webp`, `about-architecture.webp` and `approach-research.webp` are *cropped from the reference PDFs the user supplied*; verify usage rights and replace with licensed originals before launch if necessary. The brand mark and full logo were cropped/copied from the original image provided by the user.

## Design / code guide

- `/templates/base.html` — navigation, footer, Google font references
- `/templates/home.html`, `about.html`, `services.html`, `who.html`, `approach.html`, `projects.html`, `project_detail.html`, `contact.html`, `privacy.html` — page layouts
- `/content.py` — all services, audience segments, six-step approach, four detailed concept studies
- `/static/css/site.css` — colors, typography, responsive layout, motion
- `/static/js/site.js` — mobile menu, form tabs, validation and API integration
- `/app.py` — page routes, form API, SQLite storage, optional SMTP, admin login/dashboard
- `/static/assets/simt-original-logo.webp` — unmodified full logo asset
- `/static/assets/simt-original-mark.png` — extracted original logo mark
- `/tests/` — API and page tests

## Run tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

**Status:** local full-stack functionality implemented and tested. No live deployment or real email provider is configured yet; Calendly/WhatsApp remain intentionally off until real details are supplied.


## SIMORA assistant (testing-phase build)

The site includes a compact SIMORA robotic chat widget and a lightweight guided FAQ
endpoint at `/api/chat`. This first version uses curated SIMT information and keyword
routing; it does not call a generative AI model and does not require an API key. It is
suitable for a low-traffic university-project demonstration. To make SIMORA genuinely
generative, connect a server-side AI provider later and keep its API key in hosting
environment variables (never in browser JavaScript).

The chat does not currently collect or store visitor details. It provides routes to
SIMT's contact, WhatsApp and Calendly channels.

## Deployment and inquiry storage

SQLite is suitable for local development on the Windows laptop. Vercel's serverless
runtime does not provide a durable writable project filesystem, so the current SQLite
inquiry store must not be used as the production database there. Before relying on live
contact submissions, configure a hosted persistent database (for example managed
PostgreSQL) and update the database adapter. Do not change `DATABASE_PATH` to `/tmp`
as a production fix: that storage is temporary and can disappear between invocations.

Set `WHATSAPP_NUMBER=923104405529` in the deployment environment if overriding the
default website link. The SIMT WhatsApp Business greeting/away messages are configured
inside the WhatsApp Business app and are not activated by this website code.


## Visual refinement update

The latest aesthetic refresh preserves the SIMT ivory, charcoal and copper palette while improving spacing, typography hierarchy, card interactions and small-screen layouts. The header and footer now use a transparent-canvas copy of the supplied logo mark, avoiding the visible white square around the artwork. The hero logo stage no longer has a hard rectangular border; it uses a soft radial field and restrained corner framing instead. SIMORA's launcher is now a compact robot-only floating button, with a larger touch-friendly chat panel on phones. Motion is subtle and respects `prefers-reduced-motion`.


## SIMORA assistant (context-aware guided update)

SIMORA now uses a context-aware guided conversation flow rather than matching only the latest message to a single FAQ keyword. The browser keeps a short rolling conversation history and sends it with each message; the server uses that context to suggest relevant SIMT services and ask more useful follow-up questions. The conversation is kept in the visitor's browser session and is not written to the inquiry database.

This remains a curated, rule-based assistant. It is **not a generative AI model** and does not require an external API key. It cannot reliably answer arbitrary questions outside SIMT's supplied business information. A future generative upgrade would require selecting a provider, reviewing privacy and retention settings, and storing its API key only in server-side environment variables.


## Homepage Living Strategy Network (Phase 3)

The homepage hero visual now uses a lightweight inline SVG strategy network on the existing ivory background. It connects a central SIMT strategy node with market research, competitor insight, growth pathways, marketing channels, customer insights and market entry. Copper connection paths animate with subtle pulses; the visual scales for mobile and includes reduced-motion handling. The existing hero headline, calls to action, SIMT logo asset, caption and remaining homepage sections are retained.


## Phase 4 — Website polish

The shared site shell now includes page-specific Open Graph title/description metadata, a light color-scheme hint, and index/follow metadata. Main and mobile navigation expose the current page to assistive technology. The mobile navigation now keeps keyboard focus within its link list while open and returns focus to the menu button when dismissed with Escape. The inquiry form preserves the selected inquiry/consultation tab after a successful reset. SIMORA is labelled accurately as a guided assistant rather than implying a generative AI model. Reduced-motion handling now also disables smooth scrolling and nonessential hover movement.


## Phase 5 — Calendly booking notifications

The Contact page continues to use Calendly as the booking system. Calendly itself sends the invitee's booking confirmation/calendar invitation; the website does not send a second, potentially confusing confirmation email. The SIMT site can also receive signed Calendly webhooks for `invitee.created` and `invitee.canceled`, record booking status in the admin dashboard, and send an internal alert to `SIMT_EMAIL` using the configured SMTP account.

### Enable the SIMT booking alerts

1. Deploy the site to a public HTTPS URL.
2. Create a Calendly webhook subscription for `invitee.created` and `invitee.canceled`, pointing to `https://YOUR-DOMAIN/api/webhooks/calendly`.
3. Use a Calendly webhook signing key when creating the subscription, then set the same value as `CALENDLY_WEBHOOK_SIGNING_KEY` in the hosting environment.
4. Configure SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`, and `SIMT_EMAIL`) so internal booking alerts can be delivered.
5. Make a real test booking and cancellation in Calendly. Past bookings do not trigger webhooks.
6. Confirm the event appears in `/admin` and that the SIMT inbox receives the alert.

The endpoint validates the Calendly HMAC signature and its timestamp (180-second replay window), ignores unsupported event types, and avoids duplicate booking-created notifications. Cancellations update the corresponding invitee record. Do not expose the signing key or SMTP credentials in browser code or source control.

**Not yet activated:** this source package does not contain SIMT's Calendly API token or webhook signing key, and no webhook subscription can be created from the website alone. Calendly account setup, public deployment, real SMTP credentials, and an end-to-end live booking test are still required. Calendly's own confirmation email must be enabled/checked in the Calendly event type's Notifications and workflows settings.


## Phase 7 — Vercel deployment and persistent database

The project now includes Vercel's FastAPI entrypoint configuration and a PostgreSQL adapter. Local development continues to use SQLite by default. When `DATABASE_URL` is set, the app uses PostgreSQL; on Vercel, the app refuses inquiry/webhook database writes if `DATABASE_URL` is missing instead of silently writing leads to temporary function storage.

### Before deploying to Vercel

1. Create a managed PostgreSQL database with a provider of your choice (for example, Neon or another PostgreSQL host).
2. Copy its pooled or standard connection string into the Vercel project's `DATABASE_URL` environment variable. Keep the connection string private.
3. Add `SIMT_EMAIL`, `ADMIN_PASSWORD` (at least 12 characters), `SESSION_SECRET` (a separate long random value), SMTP settings, `WHATSAPP_NUMBER`, `CALENDLY_URL`, and `CALENDLY_WEBHOOK_SIGNING_KEY` as Vercel environment variables where applicable.
4. Import the project repository into Vercel and deploy. The root `app.py` exports the FastAPI `app`; `vercel.json` includes the Jinja templates and static assets in the function bundle.
5. Check `/health`. On Vercel, `persistent_storage_ready` must be `true` and `database_backend` must be `postgresql`.
6. Submit a test inquiry and confirm it appears in `/admin`; then test the Calendly webhook with a new booking and cancellation.
7. Configure SMTP and verify actual email delivery. A successful local test does not prove the hosting provider's SMTP connection or credentials are valid.

### Storage safety

Do not deploy the SQLite `data/simt.sqlite3` file as the live lead database on Vercel. Vercel Functions use ephemeral execution environments; use the configured managed PostgreSQL service for durable inquiries and booking records. SQLite remains the default for local Windows development and Docker with its persistent volume.

**Deployment status:** deployment configuration and PostgreSQL support are prepared, but no Vercel project, database URL, SMTP credentials, Calendly webhook secret, or account access was supplied. A live deployment and real external-service verification have therefore not been performed.


## Design and booking-email refinement

The homepage strategy graphic has been simplified: the floating Urdu caption card and decorative corner frame have been removed, the network has more breathing room, and its six strategy nodes are now keyboard-accessible links to related service sections. Subtle motion and hover/focus feedback have been extended across page introductions, cards, links, images, buttons and form controls. Reduced-motion preferences are still respected.

The Calendly webhook now sends two separate transactional messages after a new booking or cancellation:
- An internal SIMT alert to `SIMT_EMAIL`.
- A branded HTML + plain-text message to the invitee, using the invitee's name, booking title, date/time, timezone and any booking preparation answers supplied in the webhook payload.

**Important rollout order to avoid duplicate customer emails:** first deploy and configure the webhook signing key + SMTP, then make a real test booking and confirm that the SIMT-branded email arrives correctly. Only after that test succeeds, open the Calendly event type's Notifications and workflows settings and turn off the standard invitee confirmation email if you want the SIMT email to be the only customer-facing confirmation. Calendly remains the booking system and continues to provide its reschedule/cancel links in the booking flow; the custom email explains that customers can use the original Calendly invitation for those controls.


## Homepage hero restoration and 3D motion refinement

The homepage hero markup has been restored byte-for-byte from the originally uploaded `SIMT_Fullstack_Website_Aesthetic_Refresh.zip`: the original large SIMT direction emblem, Urdu `سمت` caption card, English “Direction with intent.” caption, headline, and original layout are back. The later six-node strategy-network hero is no longer used on the homepage.

Only the decorative copper corner-frame overlay around the hero emblem has been removed. The original brand artwork and caption panel remain. The emblem now has a restrained floating 3D animation and desktop pointer-responsive tilt; the caption has subtle depth/parallax. Content cards and image panels have more noticeable lift/depth interactions, while the existing reveal-on-scroll motion is retained. Motion is disabled or reduced when the visitor has enabled `prefers-reduced-motion`.


## Redesign v2 — "Direction That Drives Growth" visual system

This release replaces the visual layer only. Routes, forms, admin, Calendly webhooks, SIMORA's API and the database layer are unchanged.

**What changed**
- `static/css/site.css` was rebuilt as one ordered design system (tokens → base → header → buttons → hero → sections → pages → forms → admin → SIMORA → motion → responsive). Palette: ivory `#F7F3EC`, linen `#ECE5D8`, charcoal `#222426`, bright copper `#C4642D` (graphics) and deep copper `#9E4A1E` (text and buttons, for contrast). Type: Fraunces (headlines), Instrument Sans (body), DM Mono (labels), Noto Nastaliq Urdu (سمت).
- `templates/home.html`: new hero with the animated strategy network (inline SVG; each node links to a real service anchor; a separate mobile layout keeps labels legible), then perspective, approach path, eight service tiles, value, trust band, audiences and final call to action.
- `templates/base.html`: sticky header with a Contact link and "Book a consultation" button, redesigned SIMORA mascot (one SVG symbol reused in the launcher and chat header), footer restyle.
- `templates/partials/macros.html`: reusable stepped-path graphic panel (replaces the photos).
- `about`, `services`, `approach`: equal diamond-monogram team cards, expandable service cards (a link such as `/services#market-research` opens that card), stepped approach path.
- `static/js/site.js`: removed the emblem tilt; added header scroll state and open-on-hash for services.
- Removed `home-consultancy.webp`, `about-architecture.webp` and `approach-research.webp` (cropped from reference PDFs; usage rights unclear). The original logo assets are kept.
- Tests: the old hero test was replaced by `test_homepage_strategy_visual_and_brand_hero` and `test_redesign_pages_render_key_sections` (15 tests pass).

**Motion and accessibility:** all animation is CSS and stops under `prefers-reduced-motion`; strategy nodes are keyboard-focusable links; touch targets are at least 44px.

**Still to confirm before launch**
- Team emails (`@simt.com` in `app.py`) look like placeholders; confirm or replace.
- Fonts load from Google Fonts (disclosed in the privacy notice); self-host them if you prefer.
- No achievements, testimonials, statistics or case studies were added; the concept projects keep their "illustrative only" labelling.

## Deploying: GitHub → Vercel

1. Create a GitHub repository and upload the contents of this folder so that `app.py` sits at the repository root. `.gitignore` already excludes `.env` and local SQLite files.
2. In Vercel choose Add New → Project, import the repository and keep the detected FastAPI settings.
3. Add environment variables: `DATABASE_URL` (managed PostgreSQL, e.g. Neon), `ADMIN_PASSWORD` (12+ characters), `SESSION_SECRET` (a separate long random value), `SIMT_EMAIL`, the SMTP settings, `WHATSAPP_NUMBER=923104405529`, `CALENDLY_URL=https://calendly.com/simt-consultancy007/30min`, and optionally `CALENDLY_WEBHOOK_SIGNING_KEY`.
4. Deploy, then open `/health` and confirm `persistent_storage_ready` is `true` and `database_backend` is `postgresql`.
5. Submit a test inquiry and check it in `/admin`. Without `DATABASE_URL` on Vercel, inquiries are refused rather than silently lost.
