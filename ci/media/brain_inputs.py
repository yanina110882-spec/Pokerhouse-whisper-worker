"""Source-separated media input; no downloads, model calls or authority changes."""
import hashlib

def media_sources(envelope, message, source_ref):
    speech=envelope.get('AUDIO/SPEECH')
    visual=envelope.get('VISUAL')
    ocr=envelope.get('ON_SCREEN_TEXT')
    candidates=[('DOCUMENT_TEXT',envelope.get('DOCUMENT_TEXT')),
                ('AUDIO/SPEECH',speech.get('text') if isinstance(speech,dict) else None),
                ('VISUAL',visual.get('description') if isinstance(visual,dict) else None),
                ('ON_SCREEN_TEXT',ocr.get('text') if isinstance(ocr,dict) else ocr),
                ('CAPTION',message.get('caption',envelope.get('CAPTION')))]
    return [{'channel':channel,'text':text,'source_ref':source_ref}
            for channel,text in candidates if isinstance(text,str) and text.strip()]

def render_sources(sources):
    return '\n\n'.join('['+s['channel']+']\n'+s['text'] for s in sources)

def source_manifest(sources):
    return [{'channel':s['channel'],'source_ref':s['source_ref'],
             'sha256':hashlib.sha256(s['text'].encode()).hexdigest()} for s in sources]
