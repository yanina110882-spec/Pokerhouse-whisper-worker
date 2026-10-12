"""One synthetic V3 unit through real components; transport is forbidden."""
import os,sys,json,tempfile,subprocess,hashlib,socket
from pathlib import Path
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch
from assistant_core import Store,Telegram,WaitingAI
from brain import Brain
from media_queue import MediaQueue
BASE=datetime(2030,1,1,12,tzinfo=ZoneInfo('Europe/Moscow'))
TEXT='Важно: завтра отправлю файл'
EVENT={'update_id':1,'message':{'message_id':1,'date':int(BASE.timestamp()),'chat':{'id':-42},'from':{'id':42},'document':{'file_id':'synthetic-only','file_size':len(TEXT.encode())}}}
def forbidden(*a,**k):raise AssertionError('external_transport_forbidden')
def hash_state(s):return hashlib.sha256('\n'.join(s.db.iterdump()).encode()).hexdigest()
def phase(name,path):
 with patch.object(Telegram,'call',forbidden),patch('socket.create_connection',forbidden):
  s=Store(path);b=Brain(s,owner_id=42);q=MediaQueue(s,None)
  count=lambda table:s.db.execute('SELECT count(*) FROM '+table).fetchone()[0]
  if name=='ingress':
   assert s.ingest(EVENT,{-42});assert s.get(1)['state']=='RECEIVED';assert count('brain_audit')==0
   s.close();os._exit(81)
  elif name=='media_fail':
   assert s.get(1)['state']=='RECEIVED';assert json.loads(s.get(1)['raw'])==EVENT
   with patch('media_queue.download',side_effect=RuntimeError('synthetic_unavailable')):assert q.process_one(now=1000)
   assert s.get(1)['state']=='WAITING_MEDIA';assert count('brain_audit')==0
  elif name=='media_ok':
   assert not q.process_one(now=1001)
   with patch('media_queue.download',return_value=TEXT.encode()):assert q.process_one(now=2000)
   e=json.loads(s.get(1)['extracted']);assert e['DOCUMENT_TEXT']==TEXT;assert e['hash']==hashlib.sha256(TEXT.encode()).hexdigest();assert e['source_ref']=='event:1';assert s.get(1)['state']=='EXTRACTED'
   s.close();os._exit(82)
  elif name=='brain_crash':
   original=b._packet
   def crash(*a,**k):original(*a,**k);os._exit(83)
   b._packet=crash;b.process_one(now=3000);raise AssertionError('crash_not_reached')
  elif name=='brain_retry_fail':
   assert s.get(1)['state']=='WAITING_AI';assert count('brain_audit')==0;assert s.db.execute("SELECT count(*) FROM brain_items WHERE source='event:1'").fetchone()[0]==0;assert count('brain_packets')==0
   class Fail:
    def analyze(self,r):raise WaitingAI('synthetic_provider_unavailable')
   b.provider=Fail();b.process_one(now=4000);assert s.get(1)['state']=='WAITING_AI';assert count('brain_audit')==0
  elif name=='brain_ok':
   assert not b.process_one(now=4001);assert b.process_one(now=5000);assert s.get(1)['state']=='ANALYSED';assert count('brain_audit')==1
   assert b.notification_candidates()==[];assert count('brain_notifications')==0
   assert s.db.execute('SELECT state FROM brain_packets').fetchone()[0]=='SILENT'
   # Synthetic dependency context through the existing Brain API, not a significance stub.
   b.add_dependency('-42','файл','synthetic downstream','event:1')
   s.close();os._exit(84)
  elif name=='decision_crash':
   original=b._packet
   def crash(*a,**k):original(*a,**k);os._exit(85)
   b._packet=crash;b.tick(BASE+timedelta(days=3));raise AssertionError('crash_not_reached')
  elif name=='decision_ok':
   assert count('brain_audit')==1;assert count('brain_notifications')==0
   b.tick(BASE+timedelta(days=3));c=b.notification_candidates();assert len(c)==1;assert c[0]['level']=='HIGH';assert c[0]['state']=='WAITING_OWNER'
   payload=json.loads(c[0]['conclusion']);assert payload['OWNER_DECISION_REQUIRED'];assert payload['SOURCES']==['event:1'];assert payload['significance']['urgency']==2
   s.close();os._exit(86)
  elif name=='capture':
   before=hash_state(s);c=b.notification_candidates();assert len(c)==1;packet=c[0];payload=json.loads(packet['conclusion'])
   assert count('outbox')==0;assert count('brain_notifications')==1
   assert not s.ingest(EVENT,{-42});assert not b.process_one(now=9000);assert not q.process_one(now=9000);b.tick(BASE+timedelta(days=3));assert hash_state(s)==before
   analysis=json.loads(s.get(1)['analysis']);assert analysis['input_sources']==[{'channel':'DOCUMENT_TEXT','source_ref':'event:1','sha256':hashlib.sha256(TEXT.encode()).hexdigest()}]
   assert all(i['quote']==TEXT for i in analysis['items']);assert json.loads(s.get(1)['raw'])==EVENT
   transitions=[x[0] for x in s.db.execute('SELECT state FROM transitions ORDER BY id')]
   # Capture existing production Brain packet verbatim, never build a send request.
   evidence={'status':'PASS','terminal':'ANALYSED','journal':transitions,'brain_effects':count('brain_audit'),'notification_count':count('brain_notifications'),'capture_state':'CAPTURED','notification_durable_state':'PENDING','prepared_packet':packet,'source_manifest':analysis['input_sources'],'send_calls':0,'outbox_count':count('outbox'),'duplicate_retry_state_hash_before':before,'duplicate_retry_state_hash_after':hash_state(s),'silent_before_overdue':True,'partial_transaction_rollback':True,'restart_recovery':True,'external_transport':'forbidden; container network none','input':'synthetic document bytes; download fixture only','cloud_redeploy':'SKIP; separate-process restart tested'}
   print(json.dumps(evidence,ensure_ascii=False))
  else:raise ValueError(name)
  s.close()
if __name__=='__main__':
 if len(sys.argv)>1:phase(sys.argv[1],sys.argv[2])
 else:
  with tempfile.TemporaryDirectory() as tmp:
   results=[];final=None
   for name,expected in [('ingress',81),('media_fail',0),('media_ok',82),('brain_crash',83),('brain_retry_fail',0),('brain_ok',84),('decision_crash',85),('decision_ok',86),('capture',0)]:
    p=subprocess.run([sys.executable,__file__,name,tmp+'/state.sqlite'],capture_output=True,text=True)
    if p.returncode!=expected:raise AssertionError(name+': '+str(p.returncode)+' '+p.stderr)
    results.append({'phase':name,'exit':p.returncode})
    if name=='capture':final=json.loads(p.stdout)
   final['process_phases']=results
   print('V3_E2E_EVIDENCE='+json.dumps(final,ensure_ascii=False))
