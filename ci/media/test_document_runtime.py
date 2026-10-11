import tempfile,subprocess,unittest,json
from pathlib import Path
from unittest.mock import patch
from assistant_core import Store
from media_queue import MediaQueue
from media_pipeline import process_temporary

class DocumentRuntime(unittest.TestCase):
 def test_environment_failure_stays_waiting_and_retry_recovers(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'state';s=Store(path)
   raw={'update_id':1,'message':{'message_id':1,'date':1,'chat':{'id':-42},'from':{'id':7},'document':{'file_id':'synthetic'}}}
   s.ingest(raw,{-42})
   with patch('media_queue.download',return_value=b'synthetic'),patch('media_pipeline.subprocess.run',return_value=subprocess.CompletedProcess([],70,b'',b'private diagnostic')):
    MediaQueue(s,None).process_one(now=100)
   self.assertEqual(s.get(1)['state'],'WAITING_MEDIA');self.assertEqual(s.get(1)['error_code'],'media_runtime')
   self.assertNotIn('private diagnostic',str(dict(s.get(1))));s.close();s=Store(path)
   with patch('media_queue.download',return_value=b'synthetic'),patch('media_pipeline.subprocess.run',return_value=subprocess.CompletedProcess([],0,b'valid document',b'')):
    MediaQueue(s,None).process_one(now=1000)
   self.assertEqual(s.get(1)['state'],'EXTRACTED');self.assertEqual(json.loads(s.get(1)['raw']),raw);s.close()
 def test_invalid_input_still_rejected(self):
  with patch('media_pipeline.subprocess.run',return_value=subprocess.CompletedProcess([],65,b'',b'')):
   with self.assertRaises(ValueError):process_temporary(b'bad','telegram_document')
 def test_timeout_and_missing_executable_are_runtime(self):
  for error in (subprocess.TimeoutExpired('child',30),FileNotFoundError()):
   with self.subTest(error=type(error).__name__),patch('media_pipeline.subprocess.run',side_effect=error):
    with self.assertRaises(RuntimeError):process_temporary(b'x','telegram_document')
 def test_killed_process_is_not_corrupt_document(self):
  with patch('media_pipeline.subprocess.run',return_value=subprocess.CompletedProcess([],-9,b'',b'')):
   with self.assertRaises(RuntimeError):process_temporary(b'x','telegram_document')
if __name__=='__main__':unittest.main()
