#!/usr/bin/env python3
"""Poker House Media Intelligence Worker v2.

Portable media pipeline for Telegram/Instagram inputs.
Code/config only: never persist private media or credentials in the repository.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, mimetypes, os, time
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = "1.1"

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def transcribe(path: Path, model: str = "small"):
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError("Install faster-whisper for audio transcription") from e
    m = WhisperModel(model, device=os.getenv("WHISPER_DEVICE", "cpu"),
                     compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"))
    segs, info = m.transcribe(str(path), language=None, vad_filter=True)
    segments = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segs]
    return {
        "language": info.language,
        "language_probability": info.language_probability,
        "text": " ".join(s["text"] for s in segments).strip(),
        "segments": segments,
        "engine": "faster-whisper",
    }

def image_ocr(path: Path):
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(path), lang=os.getenv("OCR_LANG", "rus+eng")).strip()
        return {"text": text, "engine": "tesseract"}
    except Exception as e:
        return {"text": "", "engine": None, "warning": str(e)}

def semantic_vision(path: Path, caption: str = ""):
    """Actual semantic image understanding through an OpenAI-compatible vision endpoint.

    The provider is intentionally swappable. Set:
      VISION_BASE_URL, VISION_API_KEY, VISION_MODEL
    No key is stored in source control.
    """
    base = os.getenv("VISION_BASE_URL", "").rstrip("/")
    key = os.getenv("VISION_API_KEY", "")
    model = os.getenv("VISION_MODEL", "")
    if not (base and key and model):
        return {
            "status": "not_configured",
            "engine": None,
            "description": "",
            "objects": [],
            "important_text": [],
            "warning": "VISION_BASE_URL / VISION_API_KEY / VISION_MODEL not configured",
        }

    try:
        import httpx
        mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        prompt = (
            "Analyze this Poker House work image accurately. Return ONLY JSON with keys: "
            "description (string), objects (array of strings), important_text (array of strings), "
            "business_relevance (string), recommended_action (string). "
            "Do not invent unreadable text. Caption/context: " + (caption or "(none)")
        )
        payload = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{data}"}}
                ],
            }],
            "temperature": 0,
        }
        with httpx.Client(timeout=90) as client:
            r = client.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"description": content, "objects": [], "important_text": [],
                      "business_relevance": "", "recommended_action": ""}
        parsed.update({"status": "ok", "engine": model})
        return parsed
    except Exception as e:
        return {"status": "error", "engine": model or None, "description": "",
                "objects": [], "important_text": [], "warning": str(e)}

def process(source_type: str, path: Path, caption: str = ""):
    started = time.time()
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    out = {
        "schema_version": SCHEMA_VERSION,
        "status": "processing",
        "source_type": source_type,
        "file": {
            "name": path.name, "mime_type": mime, "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        },
        "caption": caption,
        "speech": None,
        "on_screen_text": None,
        "visual": None,
        "errors": [],
        "metrics": {},
    }
    try:
        if source_type in ("telegram_voice", "instagram_reel") or mime.startswith(("audio/", "video/")):
            out["speech"] = transcribe(path)
        if source_type == "telegram_photo" or mime.startswith("image/"):
            out["on_screen_text"] = image_ocr(path)
            out["visual"] = semantic_vision(path, caption)
            if out["visual"].get("status") == "error":
                out["errors"].append({"stage": "semantic_vision",
                                      "message": out["visual"].get("warning", "vision error")})
        if source_type == "telegram_document":
            if mime.startswith("text/"):
                out["document_text"] = path.read_text(errors="replace")
            else:
                out["document_text"] = ""
                out["errors"].append({"stage": "document_extract",
                                      "message": "Extractor not configured for this MIME type"})
        out["status"] = "ok" if not out["errors"] else "partial"
    except Exception as e:
        out["status"] = "error"
        out["errors"].append({"stage": "process", "message": str(e)})
    out["metrics"]["wall_seconds"] = round(time.time() - started, 3)
    return out

def create_app():
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    app = FastAPI(title="Poker House Media Intelligence Worker", version=SCHEMA_VERSION)

    @app.get("/health")
    def health():
        return {"status": "ok", "schema_version": SCHEMA_VERSION}

    @app.post("/v1/process")
    async def process_upload(
        file: UploadFile = File(...),
        source_type: str = Form(...),
        caption: str = Form(""),
    ):
        allowed = {"telegram_photo", "telegram_voice", "telegram_document", "instagram_reel"}
        if source_type not in allowed:
            raise HTTPException(400, "Unsupported source_type")
        import tempfile
        suffix = Path(file.filename or "upload.bin").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = Path(tmp.name)
        try:
            result = process(source_type, tmp_path, caption)
            result["file"]["name"] = file.filename or result["file"]["name"]
            return result
        finally:
            tmp_path.unlink(missing_ok=True)

    return app

app = create_app()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-type", choices=["telegram_photo","telegram_voice","telegram_document","instagram_reel"])
    ap.add_argument("--file")
    ap.add_argument("--caption", default="")
    ap.add_argument("--output")
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    a = ap.parse_args()
    if a.serve:
        import uvicorn
        uvicorn.run("worker:app", host=a.host, port=a.port)
        return
    if not a.source_type or not a.file:
        ap.error("--source-type and --file are required unless --serve is used")
    result = process(a.source_type, Path(a.file), a.caption)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if a.output:
        Path(a.output).write_text(payload, encoding="utf-8")
    print(payload)
    raise SystemExit(0 if result["status"] in ("ok", "partial") else 1)

if __name__ == "__main__":
    main()
