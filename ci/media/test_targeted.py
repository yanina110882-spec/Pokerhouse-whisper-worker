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
