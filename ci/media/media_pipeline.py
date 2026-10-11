"""Bounded local extraction, temporary-file isolation, source separation."""
import hashlib,json,subprocess,tempfile,time,wave,zipfile
from pathlib import Path
from xml.etree import ElementTree
MAX_BYTES=20*1024*1024
MAX_TEXT=2*1024*1024

def run(args,timeout=60):
 r=subprocess.run(args,capture_output=True,timeout=timeout)
 if r.returncode:raise RuntimeError('local_tool_failed')
 return r.stdout

def document(path):
 head=path.read_bytes()[:8]
 if head.startswith(b'%PDF-'):
  from pypdf import PdfReader
  r=PdfReader(path)
  if r.is_encrypted or len(r.pages)>100:raise ValueError('pdf_limit')
  text='\n'.join((p.extract_text() or '') for p in r.pages)
 elif head.startswith(b'PK'):
  with zipfile.ZipFile(path) as z:
   if sum(i.file_size for i in z.infolist())>MAX_BYTES or len(z.infolist())>1000:raise ValueError('zip_expansion_limit')
   if 'word/document.xml' not in z.namelist():raise ValueError('unsupported_archive')
   data=z.read('word/document.xml')
   if b'<!DOCTYPE' in data or b'<!ENTITY' in data:raise ValueError('xml_entities_forbidden')
   text=' '.join(ElementTree.fromstring(data).itertext())
 else:
  data=path.read_bytes()
  if b'\0' in data:raise ValueError('unsupported_binary')
  text=data.decode('utf-8-sig',errors='strict')
 if len(text.encode())>MAX_TEXT:raise ValueError('text_limit')
 return text

def extract(path,source_type,caption='',vision=None,asr=None):
 path=Path(path)
 if path.stat().st_size>MAX_BYTES:raise ValueError('media_size_limit')
 started=time.monotonic()
 out={'source_type':source_type,'caption':caption,'speech':None,'visual':None,'on_screen_text':None,
      'errors':[],'hash':hashlib.sha256(path.read_bytes()).hexdigest(),'metrics':{}}
 with tempfile.TemporaryDirectory(prefix='ph-media-') as tmp:
  if source_type=='telegram_document':
   import sys
   # Fixed exit-code protocol: invalid input is distinct from runtime/setup failure.
   code="""import sys
try:
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
 resource.setrlimit(resource.RLIMIT_CPU,(20,20))
 from pathlib import Path
 from media_pipeline import document
except Exception:
 sys.exit(70)
try:
 text=document(Path(sys.argv[1]))
except (ValueError, UnicodeError, __import__('zipfile').BadZipFile, __import__('xml.etree.ElementTree',fromlist=['ParseError']).ParseError):
 sys.exit(65)
except Exception:
 sys.exit(70)
try:
 sys.stdout.write(text)
except Exception:
 sys.exit(70)
"""
   try:result=subprocess.run([sys.executable,'-c',code,str(path)],capture_output=True,timeout=30)
   except (OSError,subprocess.TimeoutExpired):raise RuntimeError('document_runtime_unavailable') from None
   if result.returncode==65:raise ValueError('document_extraction_rejected')
   if result.returncode!=0:raise RuntimeError('document_runtime_unavailable')
   try:out['document_text']=result.stdout.decode('utf-8')
   except UnicodeError:raise RuntimeError('document_runtime_protocol') from None
  elif source_type=='telegram_photo':
   from PIL import Image
   with Image.open(path) as im:
    if im.width*im.height>25_000_000:raise ValueError('image_pixel_limit')
    im.verify()
   langs=run(['tesseract','--list-langs']).decode()
   lang='rus+eng' if '\nrus\n' in '\n'+langs else 'eng'
   text=run(['tesseract',str(path),'stdout','-l',lang]).decode().strip()
   out['on_screen_text']={'text':text,'engine':'tesseract','languages':lang,'coverage_warning':None if 'rus' in lang else 'Russian OCR language pack unavailable'}
   out['visual']=vision(path) if vision else {'status':'not_configured','description':''}
  elif source_type in {'telegram_voice','telegram_audio','telegram_video','instagram_reel'}:
   probe=json.loads(run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)]))
   if float(probe['format']['duration'])>600:raise ValueError('duration_limit')
   wav=Path(tmp)/'audio.wav'
   run(['ffmpeg','-nostdin','-v','error','-i',str(path),'-vn','-ar','16000','-ac','1',str(wav)],120)
   with wave.open(str(wav)) as f:duration=f.getnframes()/f.getframerate()
   t=time.monotonic()
   if asr is None:
    from faster_whisper import WhisperModel
    # No implicit remote download; local model path must be provisioned.
    import os
    model=os.environ.get('WHISPER_MODEL_PATH')
    if not model:raise RuntimeError('local_asr_model_not_configured')
    engine=WhisperModel(model,device='cpu',compute_type='int8',cpu_threads=2,local_files_only=True)
    segments,info=engine.transcribe(str(wav),language=None,vad_filter=True)
    segs=[{'start':s.start,'end':s.end,'text':s.text.strip()} for s in segments]
    speech={'text':' '.join(s['text'] for s in segs),'segments':segs,'language':info.language,
            'language_probability':info.language_probability,'engine':'faster-whisper'}
   else:speech=asr(wav)
   out['speech']=speech
   out['metrics'].update(duration_seconds=duration,asr_seconds=time.monotonic()-t)
   out['metrics']['rtf']=out['metrics']['asr_seconds']/duration if duration else None
   if source_type in {'telegram_video','instagram_reel'}:
    out['errors'].append({'stage':'frames','message':'frames_vision_pending'})
  else:raise ValueError('unsupported_source_type')
 out['metrics']['wall_seconds']=time.monotonic()-started
 return out

def process_temporary(data,source_type,caption='',**kwargs):
 if len(data)>MAX_BYTES:raise ValueError('media_size_limit')
 with tempfile.TemporaryDirectory(prefix='ph-upload-') as tmp:
  path=Path(tmp)/'input.bin';path.write_bytes(data)
  return extract(path,source_type,caption,**kwargs)
