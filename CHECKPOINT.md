# Checkpoint — 2026-09-15

## Preserved architecture
One portable Media Intelligence Worker, not separate Instagram/Telegram workers.
Supported source types: instagram_reel, telegram_photo, telegram_voice, telegram_document.

## Immediate acceptance criterion
Telegram photo -> downloaded file -> actual OCR/Vision -> structured JSON -> existing Poker House Assistant text/memory path.

## Current implementation
- standardized JSON envelope
- SHA-256/dedup-ready file identity
- MIME metadata
- multilingual faster-whisper adapter
- Tesseract OCR adapter
- document text bootstrap
- error/status/timing fields
- semantic vision adapter slot

## Next
1. Attach a real semantic Vision backend to `visual`.
2. Expose HTTP POST endpoint for Make binary upload.
3. Validate with natural Telegram photo 1550 if binary is still available; otherwise next natural photo.
4. Only after endpoint passes, change Make scenario 6245187 photo route.
5. Never send results to work group; delivery remains personal Telegram only.
