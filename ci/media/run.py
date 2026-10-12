"""Only the previously failed document regression, with retry/provenance assertions."""
import unittest,json,time,sys
from test_targeted import OperationalTests
case=OperationalTests('test_media_queue_document_to_brain');result=unittest.TestResult();start=time.monotonic();case.run(result)
print('DOCUMENT_QUOTE_EVIDENCE='+json.dumps({'test':'test_media_queue_document_to_brain','status':'PASS' if result.wasSuccessful() else 'FAIL','wall_seconds':time.monotonic()-start,'assertions':getattr(case,'quote_evidence',{}),'errors':[s for _,s in result.errors+result.failures]}))
sys.exit(0 if result.wasSuccessful() else 1)
