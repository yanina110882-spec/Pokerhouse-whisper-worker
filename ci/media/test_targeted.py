import io,json,os,tempfile,unittest,zipfile,time,resource,platform,subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from assistant_core import Store
from brain import Brain
from media_pipeline import process_temporary
from media_contract import normalize_worker_result
BASE=datetime(2030,1,1,12,tzinfo=ZoneInfo('Europe/Moscow'))
GROUP=-42
class API: pass
class OperationalTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.s=Store(Path(self.tmp.name)/'synthetic.sqlite');self.b=Brain(self.s,owner_id=42)
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def image_bytes(self):
  from PIL import Image,ImageDraw,ImageFont
  im=Image.new('RGB',(1000,150),'white');d=ImageDraw.Draw(im)
  font=ImageFont.truetype(os.environ.get('POKERHOUSE_TEST_FONT','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),52)
  d.text((20,30),'SYNTHETIC 50',font=font,fill='black');out=io.BytesIO();im.save(out,format='PNG');return out.getvalue()
 def test_REAL_10_photo_no_caption_OCR(self):
  r=process_temporary(self.image_bytes(),'telegram_photo');self.assertIn('SYNTHETIC',r['on_screen_text']['text']);self.assertEqual(r['caption'],'')
 def test_REAL_11_photo_caption(self):
  r=process_temporary(self.image_bytes(),'telegram_photo','synthetic caption');self.assertEqual(r['caption'],'synthetic caption');self.assertNotIn('synthetic',r['on_screen_text']['text'])
 def test_REAL_12_no_fake_vision(self):
  r=process_temporary(self.image_bytes(),'telegram_photo');e=normalize_worker_result(r,'synthetic')
  self.assertEqual(e['status'],'WAITING_MEDIA');self.assertIn('VISUAL',e['missing'])
 def test_REAL_14_docx_extraction(self):
  out=io.BytesIO()
  with zipfile.ZipFile(out,'w') as z:z.writestr('word/document.xml','<document><p>Смета завтра</p></document>')
  r=process_temporary(out.getvalue(),'telegram_document');self.assertEqual(r['document_text'],'Смета завтра')
 def test_REAL_18_temp_cleanup(self):
  with tempfile.TemporaryDirectory() as tmp:
   old=tempfile.tempdir;tempfile.tempdir=tmp
   try:
    process_temporary(b'plain synthetic text','telegram_document')
    self.assertEqual(list(Path(tmp).iterdir()),[])
    with self.assertRaises(ValueError):process_temporary(b'\x00binary','telegram_document')
    self.assertEqual(list(Path(tmp).iterdir()),[])
   finally:tempfile.tempdir=old
 def test_media_queue_document_to_brain(self):
  from media_queue import MediaQueue
  from assistant_core import WaitingAI
  from brain_inputs import render_sources
  from unittest.mock import patch
  import hashlib
  text='Завтра отправлю файл';payload=text.encode()
  e={'update_id':1,'message':{'message_id':1,'date':int(BASE.timestamp()),'chat':{'id':GROUP},'from':{'id':123},'document':{'file_id':'synthetic'}}}
  self.s.ingest(e,{GROUP});q=MediaQueue(self.s,API())
  with patch('media_queue.download',return_value=payload):self.assertTrue(q.process_one())
  self.assertEqual(self.s.get(1)['state'],'EXTRACTED')
  envelope=json.loads(self.s.get(1)['extracted']);self.assertEqual(envelope['DOCUMENT_TEXT'],text)
  self.assertEqual(envelope['hash'],hashlib.sha256(payload).hexdigest())
  original=self.b.provider
  class RetryOnce:
   def analyze(inner,request):raise WaitingAI('synthetic_retry')
  self.b.provider=RetryOnce();self.b.process_one(now=1000)
  self.assertEqual(self.s.get(1)['state'],'WAITING_AI')
  self.assertEqual(self.s.db.execute("SELECT count(*) FROM brain_audit WHERE action='brain_applied'").fetchone()[0],0)
  self.b.provider=original;self.assertFalse(self.b.process_one(now=1001));self.b.process_one(now=2000)
  self.assertEqual(self.s.get(1)['state'],'ANALYSED')
  item=self.b.items('commitments')[0];self.assertEqual(item['quote'],text)
  provenance=self.b.explain(item['id']);self.assertEqual(provenance['source_type'],'telegram_document');self.assertEqual(provenance['event_id'],1)
  self.assertEqual(json.loads(self.s.get(1)['raw']),e)
  analysis=json.loads(self.s.get(1)['analysis']);self.assertEqual(analysis['input_sources'][0],{'channel':'DOCUMENT_TEXT','source_ref':'event:1','sha256':hashlib.sha256(payload).hexdigest()})
  self.assertTrue(all(i['quote'] in text and i['quote_channels']==['DOCUMENT_TEXT'] for i in analysis['items']))
  self.assertFalse(any(i['kind']=='owner_rules' for i in analysis['items']))
  self.assertTrue(all(i['origin']!='OWNER_CONFIRMED_FACT' for i in self.b.items('commitments')))
  def state():return list(self.s.db.iterdump())
  before=state();self.s.ingest(e,{GROUP});self.assertFalse(q.process_one(now=3000));self.assertFalse(self.b.process_one(now=3000));self.assertFalse(self.b.process_one(now=4000));self.assertEqual(state(),before)
  self.assertEqual(self.s.db.execute("SELECT count(*) FROM brain_audit WHERE event_id=1 AND action='brain_applied'").fetchone()[0],1)
  # Literal labels inside source are never stripped or converted to authority.
  literal='[DOCUMENT_TEXT]\n'+text
  self.assertEqual(render_sources([{'channel':'DOCUMENT_TEXT','text':literal,'source_ref':'synthetic'}]),literal)
  self.quote_evidence={'state':'ANALYSED','brain_applied_effects':1,'retry_before_commit':True,'duplicate_state_identical':True,'source_channel':'DOCUMENT_TEXT','quote_exact_extracted_text':True,'raw_event_preserved':True,'media_sha256_preserved':True,'owner_rights':False}
 def test_document_caption_quote_alignment(self):
  from media_queue import MediaQueue
  from assistant_core import WaitingAI
  from unittest.mock import patch
  from brain_inputs import analyze_sources
  import hashlib
  texts={'DOCUMENT_TEXT':'Завтра отправлю файл','CAPTION':'Сегодня пришлю смету'}
  payload=texts['DOCUMENT_TEXT'].encode();digest=lambda s:hashlib.sha256(s.encode()).hexdigest()
  e={'update_id':1,'message':{'message_id':1,'date':int(BASE.timestamp()),'chat':{'id':GROUP},'from':{'id':42},'document':{'file_id':'synthetic'},'caption':texts['CAPTION']}}
  self.s.ingest(e,{GROUP});q=MediaQueue(self.s,API())
  with patch('media_queue.download',return_value=payload):self.assertTrue(q.process_one())
  envelope=json.loads(self.s.get(1)['extracted']);self.assertEqual(envelope['DOCUMENT_TEXT'],texts['DOCUMENT_TEXT']);self.assertEqual(envelope['hash'],digest(texts['DOCUMENT_TEXT']))
  original=self.b.provider;requests=[];fail=[True]
  class Provider:
   def analyze(inner,request):
    source=request['sources'][0];channel=source['channel'];requests.append(channel)
    self.assertEqual(request['text'],texts[channel]);self.assertEqual(len(request['sources']),1);self.assertFalse(request['is_owner'])
    if channel=='CAPTION' and fail[0]:fail[0]=False;raise WaitingAI('synthetic_caption_retry')
    return original.analyze(request)
  self.b.provider=Provider();self.b.process_one(now=1000)
  self.assertEqual(self.s.get(1)['state'],'WAITING_AI')
  self.assertEqual(self.s.db.execute("SELECT count(*) FROM brain_audit WHERE action='brain_applied'").fetchone()[0],0)
  self.assertEqual(self.s.db.execute("SELECT count(*) FROM brain_items WHERE source='event:1'").fetchone()[0],0)
  self.assertFalse(self.b.process_one(now=1001));self.b.process_one(now=2000)
  self.assertEqual(self.s.get(1)['state'],'ANALYSED');self.assertEqual(requests,['DOCUMENT_TEXT','CAPTION']*2)
  analysis=json.loads(self.s.get(1)['analysis']);self.assertEqual({i['quote_source']['channel'] for i in analysis['items']},set(texts))
  for item in analysis['items']:
   source=item['quote_source'];channel=source['channel']
   self.assertEqual(item['quote'],texts[channel]);self.assertEqual(item['quote_channels'],[channel])
   self.assertEqual(source,{'channel':channel,'source_ref':'event:1','sha256':digest(texts[channel])})
   self.assertNotEqual(item['kind'],'owner_rules')
  self.assertEqual(analysis['input_sources'],[{'channel':c,'source_ref':'event:1','sha256':digest(t)} for c,t in texts.items()])
  items=[i for i in self.b.items('commitments') if i['source']=='event:1'];self.assertEqual(len(items),2)
  for item in items:
   source=self.b.explain(item['id']);self.assertEqual(source['event_id'],1);self.assertEqual(source['source_type'],'telegram_document');self.assertNotEqual(item['origin'],'OWNER_CONFIRMED_FACT')
  self.assertEqual(json.loads(self.s.get(1)['raw']),e)
  before=list(self.s.db.iterdump());self.s.ingest(e,{GROUP});self.assertFalse(q.process_one(now=3000));self.assertFalse(self.b.process_one(now=3000));self.assertFalse(self.b.process_one(now=4000));self.assertEqual(before,list(self.s.db.iterdump()))
  effects=self.s.db.execute("SELECT count(*) FROM brain_audit WHERE event_id=1 AND action='brain_applied'").fetchone()[0];self.assertEqual(effects,1)
  # A quote belonging only to the OTHER source is rejected at the boundary.
  class WrongSource:
   def analyze(inner,request):return {'items':[{'quote':texts['CAPTION']} ]}
  with self.assertRaisesRegex(ValueError,'ungrounded_source_extraction'):
   analyze_sources(WrongSource(),{'sources':[{'channel':c,'text':t,'source_ref':'event:1'} for c,t in texts.items()]})
  self.quote_evidence={'state':'ANALYSED','brain_applied_effects':effects,'commitments':2,'quotes':[{'quote':i['quote'],'source':i['quote_source']} for i in analysis['items']],'provider_calls':requests,'partial_failure_commits':0,'retry_before_due_skipped':True,'duplicate_full_state_identical':True,'cross_source_quote_rejected':True,'raw_event_metadata_preserved':True,'media_hash_preserved':True,'owner_sender_media_not_owner_instruction':True}
