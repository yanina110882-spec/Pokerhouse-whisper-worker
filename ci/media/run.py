"""Only mixed OCR/caption regression; prior suites are not rerun."""
import unittest,json,time,sys
from test_targeted import OperationalTests
case=OperationalTests('test_ocr_caption_quote_alignment');result=unittest.TestResult();start=time.monotonic();case.run(result)
print('OCR_CAPTION_EVIDENCE='+json.dumps({'test':'test_ocr_caption_quote_alignment','status':'PASS' if result.wasSuccessful() else 'FAIL','wall_seconds':time.monotonic()-start,'assertions':getattr(case,'quote_evidence',{}),'errors':[s for _,s in result.errors+result.failures]}))
sys.exit(0 if result.wasSuccessful() else 1)
