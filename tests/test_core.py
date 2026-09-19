"""Synthetic fixtures only: no real user IDs, messages or credentials."""
import json
import tempfile
import unittest
from pathlib import Path
from assistant_core import Store, AIRouter, WaitingAI, process_one, route, preflight, poll_once, deliver_one

GROUP = -1000000000001  # synthetic, never used against Telegram
OWNER = 42

def event(uid=1, **fields):
    return {'update_id':uid,'message':{'message_id':uid,'date':1,
            'chat':{'id':GROUP,'type':'supergroup'},'from':{'id':123,'is_bot':False},
            **(fields or {'text':'Synthetic ordinary message'})}}

class Provider:
    def __init__(self, notify=False): self.requests=[]; self.notify=notify
    def analyze(self,request):
        self.requests.append(request)
        return {'notify':self.notify,'summary':'Synthetic conclusion',
                'source_events':[request['source_event']]}

class API:
    def __init__(self,updates=(),webhook='',privacy=True):
        self.calls=[]; self.updates=updates; self.webhook=webhook; self.privacy=privacy
    def call(self,method,**params):
        self.calls.append((method,params))
        return {'getUpdates':self.updates,'getWebhookInfo':{'url':self.webhook},
                'getMe':{'can_read_all_group_messages':self.privacy},
                'getChat':{'type':'private'},'sendMessage':{'message_id':999}}[method]

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)/'state.sqlite'
        self.s=Store(self.path)
    def tearDown(self): self.s.close(); self.tmp.cleanup()

    def test_persist_before_ai_restart_recovery(self):
        poll_once(self.s,API([event()]),{GROUP})
        self.assertEqual(self.s.get(1)['state'],'RECEIVED')
        self.s.close(); self.s=Store(self.path)
        process_one(self.s,AIRouter(),now=100)
        self.assertEqual(self.s.get(1)['state'],'WAITING_AI')
        self.assertEqual(json.loads(self.s.get(1)['raw']),event())
        self.s.close(); self.s=Store(self.path)
        p=Provider()
        self.assertFalse(process_one(self.s,AIRouter([p]),now=101))
        process_one(self.s,AIRouter([p]),now=1000)
        self.assertEqual(self.s.get(1)['state'],'ANALYSED')
        self.assertEqual(self.s.offset(),2)
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM outbox').fetchone()[0],0)

    def test_duplicate_update_and_message(self):
        self.assertTrue(self.s.ingest(event(),{GROUP}))
        self.assertFalse(self.s.ingest(event(),{GROUP}))
        second=event(); second['update_id']=2
        self.assertFalse(self.s.ingest(second,{GROUP}))
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM events').fetchone()[0],1)

    def test_edits_preserved(self):
        self.s.ingest(event(),{GROUP})
        edit=event(2); msg=edit.pop('message'); msg['message_id']=1; msg['edit_date']=10
        edit['edited_message']=msg
        self.assertTrue(self.s.ingest(edit,{GROUP}))

    def test_captionless_photo_and_types(self):
        for kind in ('photo','voice','audio','document','video'):
            msg={kind:[{'file_id':'synthetic'}] if kind=='photo' else {'file_id':'synthetic'}}
            self.assertEqual(route(msg),kind)
        self.s.ingest(event(photo=[{'file_id':'synthetic'}]),{GROUP})
        process_one(self.s,AIRouter())
        self.assertEqual(self.s.get(1)['state'],'WAITING_MEDIA')

    def test_webhook_never_mutated(self):
        api=API(webhook='https://example.invalid/existing')
        with self.assertRaisesRegex(RuntimeError,'WEBHOOK_ACTIVE'): preflight(api)
        self.assertEqual([x[0] for x in api.calls],['getWebhookInfo'])

    def test_privacy_gate(self):
        with self.assertRaisesRegex(RuntimeError,'PRIVACY_MODE'): preflight(API(privacy=False))

    def test_unallowed_chat_discarded_and_cursor_committed(self):
        self.assertFalse(self.s.ingest(event(),set()))
        self.assertIsNone(self.s.get(1)); self.assertEqual(self.s.offset(),2)

    def test_history_and_inference_separation(self):
        self.s.ingest(event(),{GROUP}); p=Provider()
        process_one(self.s,AIRouter([p]))
        self.s.ingest(event(2,text='Synthetic related message'),{GROUP})
        process_one(self.s,AIRouter([p]))
        self.assertEqual(p.requests[-1]['history'][0]['source_event'],1)
        self.assertEqual(self.s.db.execute("SELECT count(*) FROM memory WHERE entity_type='fact'").fetchone()[0],0)

    def test_only_private_owner_delivery(self):
        self.s.ingest(event(),{GROUP}); process_one(self.s,AIRouter([Provider(True)]))
        api=API()
        with self.assertRaises(ValueError): deliver_one(self.s,api,GROUP,{GROUP})
        self.assertEqual(api.calls,[])
        deliver_one(self.s,api,OWNER,{GROUP})
        self.assertEqual(api.calls[-1][1]['chat_id'],OWNER)
        self.assertEqual(self.s.get(1)['state'],'DELIVERED')
        self.assertFalse(deliver_one(self.s,api,OWNER,{GROUP}))

    def test_unknown_evidence_rejected(self):
        class Bad:
            def analyze(self,request):
                return {'notify':True,'summary':'Invented','source_events':[9999]}
        self.s.ingest(event(),{GROUP}); process_one(self.s,AIRouter([Bad()]))
        self.assertEqual(self.s.get(1)['state'],'WAITING_AI')
        self.assertEqual(self.s.db.execute('SELECT count(*) FROM outbox').fetchone()[0],0)

    def test_backup_restore(self):
        self.s.ingest(event(),{GROUP})
        backup=Path(self.tmp.name)/'backup.sqlite'
        self.s.backup(backup)
        restored=Store(backup)
        self.assertEqual(restored.get(1)['raw'],self.s.get(1)['raw'])
        self.assertEqual(restored.offset(),2)
        restored.close()

    def test_failed_send_preserved_without_blind_duplicate(self):
        class Broken(API):
            def call(self,method,**params):
                if method=='sendMessage': raise RuntimeError('uncertain_transport')
                return super().call(method,**params)
        self.s.ingest(event(),{GROUP}); process_one(self.s,AIRouter([Provider(True)]))
        with self.assertRaises(RuntimeError): deliver_one(self.s,Broken(),OWNER,{GROUP})
        self.assertEqual(self.s.db.execute('SELECT state FROM outbox').fetchone()[0],'AMBIGUOUS')

if __name__=='__main__': unittest.main()
