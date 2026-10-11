"""Durable media extraction cache. No outbound messaging or webhook mutation."""
import json,re,time
from pathlib import PurePosixPath
from media_pipeline import MAX_BYTES,process_temporary
from media_contract import normalize_worker_result

def download(api,file_id):
 meta=api.call('getFile',file_id=file_id)
 if meta.get('file_size',0)>MAX_BYTES:raise ValueError('media_size_limit')
 path=meta['file_path']
 if not re.fullmatch(r'[A-Za-z0-9_./-]+',path) or '..' in PurePosixPath(path).parts or path.startswith('/'):
  raise ValueError('invalid_telegram_file_path')
 base=api.base.replace('https://api.telegram.org/bot','https://api.telegram.org/file/bot',1)
 chunks=[];size=0
 try:
  with api.client.stream('GET',base+path) as resp:
   if resp.status_code!=200:raise RuntimeError('download_failed')
   for chunk in resp.iter_bytes():
    size+=len(chunk)
    if size>MAX_BYTES:raise ValueError('media_size_limit')
    chunks.append(chunk)
 except ValueError:raise
 except Exception:raise RuntimeError('telegram_download_failed') from None
 return b''.join(chunks)

class MediaQueue:
 def __init__(self,store,api,vision=None):
  self.store=store;self.api=api;self.vision=vision
  store.db.execute('CREATE TABLE IF NOT EXISTS media_cache (hash TEXT NOT NULL,source_type TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(hash,source_type))')
  store.db.commit()
 def process_one(self,now=None):
  import hashlib
  now=time.time() if now is None else now
  row=self.store.db.execute("SELECT * FROM events WHERE kind IN ('photo','voice','audio','document','video') AND state IN ('RECEIVED','WAITING_MEDIA','DOWNLOADED') AND next_attempt<=? ORDER BY update_id LIMIT 1",(now,)).fetchone()
  if row is None:return False
  uid=row['update_id'];raw=json.loads(row['raw']);msg=raw.get('message') or raw['edited_message'];kind=row['kind'];source='telegram_'+kind
  try:
   part=msg[kind][-1] if kind=='photo' else msg[kind]
   if part.get('file_size',0)>MAX_BYTES:raise ValueError('media_size_limit')
   data=download(self.api,part['file_id']);digest=hashlib.sha256(data).hexdigest()
   self.store.transition(uid,'DOWNLOADED')
   cached=self.store.db.execute('SELECT result FROM media_cache WHERE hash=? AND source_type=?',(digest,source)).fetchone()
   result=json.loads(cached[0]) if cached else process_temporary(data,source,vision=self.vision)
   result['caption']=msg.get('caption','')
   envelope=normalize_worker_result(result,'event:'+str(uid));envelope['hash']=digest
   if envelope['status']=='EXTRACTED':
    with self.store.db:self.store.db.execute('INSERT OR REPLACE INTO media_cache VALUES (?,?,?)',(digest,source,json.dumps(result)))
   self.store.transition(uid,envelope['status'],extracted=json.dumps(envelope),next_attempt=now+300 if envelope['status']=='WAITING_MEDIA' else 0,error_code='incomplete_media' if envelope['status']=='WAITING_MEDIA' else None)
   return True
  except Exception as exc:
   n=row['attempts']+1
   # No raw exception URLs/credential strings in DB or logs.
   self.store.transition(uid,'FAILED' if isinstance(exc,ValueError) else 'WAITING_MEDIA',attempts=n,
                         error_code='media_validation' if isinstance(exc,ValueError) else 'media_runtime',next_attempt=now+min(86400,60*2**min(n,10)))
   return True
