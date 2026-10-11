import json,time,sys,unittest,resource,platform,subprocess,os
from pathlib import Path
from test_targeted import OperationalTests
from test_document_runtime import DocumentRuntime
import socket
interfaces=sorted(x.name for x in Path('/sys/class/net').iterdir())
assert interfaces==['lo'],interfaces
sock=socket.socket();sock.settimeout(1)
try:
 sock.connect(('192.0.2.1',443));raise AssertionError('unexpected network route')
except OSError as e:network_error=e.errno
finally:sock.close()
report=[]
for cls in [OperationalTests,DocumentRuntime]:
 for name in unittest.defaultTestLoader.getTestCaseNames(cls):
  r=unittest.TestResult();start=time.monotonic();before=resource.getrusage(resource.RUSAGE_SELF);cls(name).run(r);after=resource.getrusage(resource.RUSAGE_SELF)
  report.append({'test':name,'status':'FAIL' if r.failures or r.errors else 'PASS','wall_seconds':time.monotonic()-start,'parent_cpu_seconds':after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,'errors':[v for _,v in r.errors+r.failures]})
# Real kernel enforcement without approaching container OOM.
probe="""import resource,json
cap=512*1024*1024
resource.setrlimit(resource.RLIMIT_AS,(cap,cap));resource.setrlimit(resource.RLIMIT_CPU,(20,20))
try: b=bytearray(cap); rejected=False
except MemoryError: rejected=True
print(json.dumps({'RLIMIT_AS':resource.getrlimit(resource.RLIMIT_AS),'RLIMIT_CPU':resource.getrlimit(resource.RLIMIT_CPU),'oversized_allocation_rejected':rejected}))
assert rejected
"""
p=subprocess.run([sys.executable,'-c',probe],capture_output=True,text=True,check=True)
cgroup={}
for k in ['memory.max','memory.peak','cpu.max','memory.events']:
 f=Path('/sys/fs/cgroup')/k;cgroup[k]=f.read_text().strip() if f.exists() else 'UNKNOWN'
assert cgroup['memory.max']=='805306368',cgroup
assert cgroup['cpu.max'].split()[0]==cgroup['cpu.max'].split()[1],cgroup
assert os.getuid()!=0
print('MEDIA_CI_EVIDENCE='+json.dumps({'platform':platform.platform(),'python':sys.version,'tests':report,'limits':json.loads(p.stdout),'cgroup':cgroup,'uid':os.getuid(),'network':{'interfaces':interfaces,'external_connect_errno':network_error},'dependencies':{'pillow':__import__('PIL').__version__,'pypdf':__import__('pypdf').__version__},'peak_memory_scope':'cgroup memory.peak includes container processes; not Cloudflare DO','full_DO_peak_memory':'UNKNOWN'},ensure_ascii=True))
sys.exit(1 if any(x['status']!='PASS' for x in report) else 0)
