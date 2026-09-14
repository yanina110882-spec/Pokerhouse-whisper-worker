#!/usr/bin/env python3
"""Poker House Media Intelligence Worker.
Portable media pipeline for Telegram/Instagram inputs.
No private media or credentials are persisted in the repository.
"""
from __future__ import annotations
import argparse, json, hashlib, mimetypes, os, subprocess, tempfile, time
from pathlib import Path

SCHEMA_VERSION = "1.0"

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def run(cmd):
    p=subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode: raise RuntimeError(p.stderr.strip() or 'command failed')
    return p.stdout

def transcribe(path: Path, model='small'):
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError('Install faster-whisper for audio transcription') from e
    m=WhisperModel(model, device='cpu', compute_type='int8')
    segs, info=m.transcribe(str(path), language=None, vad_filter=True)
    segments=[{'start':s.start,'end':s.end,'text':s.text.strip()} for s in segs]
    return {'language':info.language,'language_probability':info.language_probability,
            'text':' '.join(s['text'] for s in segments).strip(),'segments':segments}

def image_ocr(path: Path):
    # OCR is optional; vision provider can be attached later without changing output schema.
    try:
        import pytesseract
        from PIL import Image
        text=pytesseract.image_to_string(Image.open(path), lang='rus+eng').strip()
        return {'text':text,'engine':'tesseract'}
    except Exception as e:
        return {'text':'','engine':None,'warning':str(e)}

def process(source_type: str, path: Path, caption: str=''):
    started=time.time(); mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    out={'schema_version':SCHEMA_VERSION,'status':'processing','source_type':source_type,
         'file':{'name':path.name,'mime_type':mime,'sha256':sha256(path),'size_bytes':path.stat().st_size},
         'caption':caption,'speech':None,'on_screen_text':None,'visual':None,'errors':[], 'metrics':{}}
    try:
        if source_type in ('telegram_voice','instagram_reel') or mime.startswith(('audio/','video/')):
            out['speech']=transcribe(path)
        if source_type=='telegram_photo' or mime.startswith('image/'):
            out['on_screen_text']=image_ocr(path)
            out['visual']={'status':'vision_adapter_pending','note':'OCR is active; semantic vision adapter plugs into this field.'}
        if source_type=='telegram_document':
            if mime.startswith('text/'):
                out['document_text']=path.read_text(errors='replace')
            else:
                out['document_text']=''
                out['errors'].append({'stage':'document_extract','message':'Extractor not configured for this MIME type'})
        out['status']='ok' if not out['errors'] else 'partial'
    except Exception as e:
        out['status']='error'; out['errors'].append({'stage':'process','message':str(e)})
    out['metrics']['wall_seconds']=round(time.time()-started,3)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-type', required=True, choices=['telegram_photo','telegram_voice','telegram_document','instagram_reel'])
    ap.add_argument('--file', required=True); ap.add_argument('--caption', default=''); ap.add_argument('--output')
    a=ap.parse_args(); result=process(a.source_type, Path(a.file), a.caption)
    payload=json.dumps(result, ensure_ascii=False, indent=2)
    if a.output: Path(a.output).write_text(payload, encoding='utf-8')
    print(payload)
    raise SystemExit(0 if result['status'] in ('ok','partial') else 1)
if __name__=='__main__': main()
