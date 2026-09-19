# Pokerhouse Media Intelligence Worker

Portable code-only worker for Poker House media intelligence.

## Current checkpoint
`telegram_photo -> downloaded file -> OCR + semantic Vision -> structured JSON -> Poker House Assistant`

## HTTP endpoint
Run:

```bash
pip install -r requirements.txt
python worker.py --serve
```

Health:
`GET /health`

Process media:
`POST /v1/process` as multipart/form-data:
- `file`: binary media
- `source_type`: `telegram_photo`, `telegram_voice`, `telegram_document`, or `instagram_reel`
- `caption`: optional text

## Vision
Semantic image understanding uses an OpenAI-compatible vision endpoint so the runtime/provider can be replaced without changing Make.

Runtime environment variables:
- `VISION_BASE_URL`
- `VISION_API_KEY`
- `VISION_MODEL`

Credentials are runtime secrets only. Never commit them.

If Vision is not configured, the worker explicitly returns `visual.status = not_configured`; it never pretends OCR is semantic image understanding.

## Safety
Never commit Telegram/Instagram media, transcripts, cookies, tokens, credentials or session data.


## V3 Assistant Core — first milestone, not production-ready
V2 processing code is preserved. `assistant_core.py` adds direct polling,
SQLite ingestion, a retry queue, provenance/history and an owner-only outbox.
No Work/Make imports or runtime dependency.

Tests: `python -m unittest discover -s tests -v` (synthetic fixtures only).
`Dockerfile.core`/`compose.core.yml` define separate listener/processor services
and a persistent volume. No deployment runs automatically from this repository.
On a verified free host, secrets belong in `/etc/pokerhouse/assistant.env`, mode
0600, with TELEGRAM_BOT_TOKEN and ALLOWED_CHAT_IDS. Never commit actual values.

`python assistant_core.py preflight` checks Telegram read-only; an active webhook
or privacy mode blocks startup without mutation. `poll` must not run on the
production bot before controlled acceptance. `process` uses an empty AI router
by default and keeps text in WAITING_AI. Non-text events stay WAITING_MEDIA until
a durable V2 adapter is wired. One process per role is enforced using file locks.
The tested private-owner delivery function is not enabled as a daemon. Uncertain
send results stay AMBIGUOUS because Telegram has no send idempotency key.
Ordinary analyzed events stay ANALYSED with no outbox entry.

`backup --destination <private-path>` creates an integrity-checked SQLite snapshot.
Off-VM backup and actual media/AI/reboot/live-group tests remain pending.
See CHECKPOINT.md and RUNTIME_REVIEW.md. Do not expose the V2 upload API publicly
without authentication, resource limits and a separate security review.
