# Checkpoint — 2026-09-15 — v2

## Preserved architecture
One portable Media Intelligence Worker for Instagram and Telegram.

## Implemented in v2
- stable JSON envelope / SHA-256 identity
- multilingual faster-whisper
- Tesseract OCR
- actual semantic Vision adapter via swappable OpenAI-compatible endpoint
- FastAPI `POST /v1/process` multipart endpoint for Make
- `GET /health`
- temporary upload deletion after processing
- explicit `not_configured` state: OCR is never mislabeled as Vision

## Immediate next acceptance test
Deploy worker to a suitable cloud runtime, configure a Vision provider as a runtime secret, then:
`telegram_photo -> Make Download File -> POST /v1/process -> actual visual description + OCR -> structured JSON`

Do not modify Make scenario 6245187 until the endpoint passes a real photo test.

## Routing invariant
Results/notifications go only to the owner's personal Telegram. Never send to the Poker House work group.

## Security
No private media, transcripts, tokens, API keys, cookies or sessions in GitHub.
