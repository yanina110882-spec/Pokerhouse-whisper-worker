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
