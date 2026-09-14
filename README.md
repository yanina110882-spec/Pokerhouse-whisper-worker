# Pokerhouse Media Intelligence Worker

Portable code-only worker for Poker House media intelligence. It accepts Telegram photos, voice messages and documents plus Instagram Reels, and emits one stable JSON envelope for the Poker House Assistant.

## First checkpoint
`telegram_photo -> file -> OCR/Vision -> structured JSON`

The current bootstrap implements file hashing, MIME detection, Tesseract OCR, multilingual faster-whisper ASR, standardized JSON, errors and timing. Semantic image vision is deliberately isolated behind the `visual` field so a free/local or cloud runtime can be swapped without changing Make or the assistant contract.

## Safety
Do not commit Telegram/Instagram media, transcripts, cookies, tokens, credentials or session data. Repository is code/config documentation only.

## Example
```bash
python worker.py --source-type telegram_photo --file photo.jpg --caption "optional caption" --output result.json
```
