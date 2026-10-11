"""Synthetic project Brain: local explicit-language adapter + durable reasoning policy.

No network, billing, Telegram sends or secret configuration in this module.
Uncertain extraction is never promoted to an owner-confirmed fact.
"""
import json
import re
import time
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo
from assistant_core import WaitingAI
from brain_inputs import media_sources, render_sources, source_manifest

KINDS = {'people','entities','facts','decisions','tasks','commitments','deadlines',
         'issues','risks','open_loops','financial_events','marketing_experiments',
         'knowledge_items','ai_inferences','owner_feedback','owner_rules'}
STATUSES = {'CONFIRMED','PROBABLE','UNVERIFIED','CONFLICTING','SUPERSEDED'}
CATEGORIES = 'OPENING OPERATIONS MARKETING CONTENT BRAND FINANCE BAR HR IT_AI LEGAL'.split()
TZ = ZoneInfo('Europe/Moscow')
OPENING = datetime(2030,1,1,19,tzinfo=TZ)


def dumps(value): return json.dumps(value,ensure_ascii=False,sort_keys=True)


def deadline(text, at):
    """Explicit day expressions yield ranges, never an invented exact time."""
    low=text.lower(); day=None; expression=None
    for expr,delta in [('через неделю',7),('завтра',1),('сегодня',0)]:
        if expr in low:
            day=(at+timedelta(days=delta)).date(); expression=expr; break
    weekdays=['понедельник','вторник','сред','четверг','пятниц','суббот','воскресень']
    if day is None:
        for i,name in enumerate(weekdays):
            m=re.search(r'(?:(?:к|в|до)\s+)?'+name+r'\w*',low)
            if m:
                day=(at+timedelta(days=(i-at.weekday())%7)).date();expression=m.group();break
    months=['январ','феврал','март','апрел','ма','июн','июл','август','сентябр','октябр','ноябр','декабр']
    match=re.search(r'\b(\d{1,2})[./](\d{1,2})(?:[./](\d{4}))?\b',low)
    if match:
        try: day=datetime(int(match[3] or at.year),int(match[2]),int(match[1])).date();expression=match.group()
        except ValueError: return None
    else:
        for month,name in enumerate(months,1):
            m=re.search(r'\b(\d{1,2})\s+'+name+r'\w*',low)
            if m:
                try: day=datetime(at.year,month,int(m[1])).date();expression=m.group()
                except ValueError: return None
                break
    if 'до открытия' in low:
        return {'original_expression':'до открытия','start':None,'end':OPENING.isoformat(),'kind':'HARD','timezone':str(TZ)}
    evening='вечером' in low
    if evening and day is None: day=at.date();expression='вечером'
    if day is None: return None
    start=datetime.combine(day,dtime(18 if evening else 0),TZ)
    end=datetime.combine(day,dtime(23,59,59),TZ)
    return {'original_expression':expression+(' вечером' if evening and expression!='вечером' else ''),
            'start':start.isoformat(),'end':end.isoformat(),
            'kind':'SOFT' if evening else 'HARD','timezone':str(TZ),
            'precision':'day_range' if not evening else 'evening_range',
            'normalization_policy':'evening=18:00..23:59:59; configurable policy, not quoted time'}


class LocalRulesProvider:
    """Conservative finite grammar. Not a general LLM or semantic Vision model."""
    def analyze(self, request):
        text=request['text']; low=text.lower(); items=[]
        topic=None
        for word,key in [('смет','смета'),('файл','файл'),('макет','макеты'),('съём','съёмка'),('съем','съёмка'),('договор','договор')]:
            if word in low: topic=key; break
        # Resolve pronouns only if there is exactly one active candidate in scope.
        if topic is None and re.search(r'\b(он|она|опять|перен[её]с)',low):
            candidates=request.get('active_topics',[])
            if len(candidates)==1: topic=candidates[0]
        if request['is_owner'] and topic is None and len(request.get('active_topics',[]))==1:
            topic=request['active_topics'][0]
        if topic and deadline(text,request['at']):
            items.append({'kind':'facts','key':topic+':deadline','value':deadline(text,request['at']), 'quote':text})
        if 'кухн' in low:
            items.append({'kind':'facts','key':'kitchen','value':not bool(re.search(r'нет кухни|кухни нет|без кухни',low)), 'quote':text})
        if topic and (deadline(text,request['at']) or re.search(r'отправлю|пришлю|уточню|согласую|готово|перен',low)):
            action='complete' if re.search(r'отправил[аи]?\b|прислал[аи]?\b|готово\b',low) and not re.search(r'будет|завтра|к пятниц',low) else 'promise'
            if re.search(r'перен[её]с|перенос',low): action='postpone'
            items.append({'kind':'commitments','key':topic,'value':text,'quote':text,'action':action,
                          'important':bool(re.search(r'важн|критич|открыти',low))})
        elif re.search(r'я уточню|вечером пришлю',low):
            items.append({'kind':'commitments','key':'уточнение' if 'уточню' in low else 'отправка',
                          'value':text,'quote':text,'action':'promise','important':False})
        if re.search(r'жд[её]м|нужно выбрать|нужно подтвердить|требуется решение|должны согласовать',low):
            items.append({'kind':'open_loops','key':topic or low,'value':text,'quote':text})
        if re.search(r'счет|счёт|стоимость|оплат|бюджет',low):
            match=re.search(r'(\d[\d ]*(?:[.,]\d+)?)\s*(руб|₽|usd|eur)',low)
            amount=float(match[1].replace(' ','').replace(',','.')) if match else None
            items.append({'kind':'financial_events','key':topic or 'finance', 'quote':text,
                          'value':{'vendor':None,'category':'FINANCE','quoted_amount':amount,
                                   'approved_amount':None,'paid_amount':None,'currency':('RUB' if match and match[2] in ('руб','₽') else match[2].upper() if match else None),
                                   'due_date':None,'payment_status':'UNVERIFIED','project':'Synthetic project'}})
        if re.search(r'предполагаю|возможно|кажется',low):
            items=[{'kind':'ai_inferences','key':topic or 'hypothesis','value':text,'quote':text}]
        if request['is_owner']:
            for phrase,mode in [('не отвлекай','mute'),('это неважно','mute'),('сообщай сразу','immediate'),('второй раз','second_delay')]:
                if phrase in low:
                    items.append({'kind':'owner_rules','key':request.get('feedback_topic') or topic or 'general',
                                  'value':mode,'quote':text});break
        return {'items':items,'method':'local_explicit_rules_v1','unparsed':not bool(items)}


class Brain:
    def __init__(self, store, provider=None, owner_id=None):
        self.store=store;self.db=store.db;self.provider=provider or LocalRulesProvider();self.owner_id=owner_id
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS brain_sources (
          id TEXT PRIMARY KEY, event_id INTEGER REFERENCES events(update_id), source_type TEXT NOT NULL,
          author TEXT, timestamp TEXT NOT NULL, method TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS brain_items (
          id INTEGER PRIMARY KEY, kind TEXT NOT NULL, scope TEXT NOT NULL, item_key TEXT NOT NULL,
          value TEXT NOT NULL, knowledge_status TEXT NOT NULL, origin TEXT NOT NULL,
          source TEXT NOT NULL REFERENCES brain_sources(id), confidence REAL NOT NULL,
          quote TEXT NOT NULL, supersedes INTEGER REFERENCES brain_items(id), created_at REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS brain_lookup ON brain_items(scope,kind,item_key);
        CREATE TABLE IF NOT EXISTS brain_commitments (
          scope TEXT NOT NULL, topic TEXT NOT NULL, who TEXT NOT NULL, what TEXT NOT NULL,
          created_at TEXT NOT NULL, expected_at TEXT, deadline_json TEXT,
          status TEXT NOT NULL, completion_source TEXT REFERENCES brain_sources(id),
          source TEXT NOT NULL REFERENCES brain_sources(id), delays INTEGER NOT NULL DEFAULT 0,
          important INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(scope,topic,who));
        CREATE TABLE IF NOT EXISTS brain_dependencies (
          scope TEXT NOT NULL, prerequisite TEXT NOT NULL, dependent TEXT NOT NULL,
          source TEXT NOT NULL REFERENCES brain_sources(id), PRIMARY KEY(scope,prerequisite,dependent));
        CREATE TABLE IF NOT EXISTS brain_packets (
          scope TEXT NOT NULL, topic TEXT NOT NULL, level TEXT NOT NULL,
          conclusion TEXT NOT NULL, sources TEXT NOT NULL, decision_required INTEGER NOT NULL,
          revision INTEGER NOT NULL, notified_revision INTEGER NOT NULL DEFAULT 0,
          state TEXT NOT NULL, PRIMARY KEY(scope,topic));
        CREATE TABLE IF NOT EXISTS brain_decisions (
          scope TEXT NOT NULL, topic TEXT NOT NULL, sources TEXT NOT NULL,
          state TEXT NOT NULL, resolution_source TEXT REFERENCES brain_sources(id),
          PRIMARY KEY(scope,topic));
        CREATE TABLE IF NOT EXISTS brain_workstreams (
          category TEXT PRIMARY KEY, state TEXT NOT NULL, source TEXT NOT NULL REFERENCES brain_sources(id));
        CREATE TABLE IF NOT EXISTS brain_jobs (
          event_id INTEGER PRIMARY KEY REFERENCES events(update_id), state TEXT NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0, updated_at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS brain_audit (
          id INTEGER PRIMARY KEY, event_id INTEGER, action TEXT NOT NULL, at REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS brain_notifications (
          scope TEXT NOT NULL, topic TEXT NOT NULL, revision INTEGER NOT NULL,
          state TEXT NOT NULL, PRIMARY KEY(scope,topic,revision));
        ''')
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO brain_sources VALUES ('owner-spec',NULL,'OWNER_SPEC','owner',?,'owner_explicit')",('2030-01-01',))
            canonical={'name':'Synthetic project','opening':OPENING.isoformat(),'hours':'synthetic','seats':1,'tables':1,'format':'synthetic','kitchen':False,'bar':['synthetic'],'brand':'synthetic','motifs':['synthetic'],'visual':'synthetic'}
            for key,value in canonical.items():
                if not self.db.execute("SELECT 1 FROM brain_items WHERE scope='canonical' AND item_key=?",(key,)).fetchone():
                    self._item('facts','canonical',key,value,'CONFIRMED','OWNER_CONFIRMED_FACT','owner-spec',1,'Explicit owner specification')

    def _item(self,kind,scope,key,value,status,origin,source,confidence,quote,supersedes=None):
        if kind not in KINDS or status not in STATUSES: raise ValueError('invalid_memory_type')
        return self.db.execute('''INSERT INTO brain_items(kind,scope,item_key,value,knowledge_status,origin,source,confidence,quote,supersedes,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)''',(kind,scope,key,dumps(value),status,origin,source,confidence,quote,supersedes,time.time())).lastrowid

    def items(self,kind=None):
        return [dict(r) for r in self.db.execute('SELECT * FROM brain_items'+(' WHERE kind=?' if kind else ''),(kind,) if kind else ())]

    def _fact(self,item,scope,source,is_owner):
        kind=item['kind'];key=item['key'];value=item['value']
        origin='AI_INFERENCE' if kind=='ai_inferences' else 'OWNER_DECISION' if is_owner else 'EXTRACTED_FACT'
        status='CONFIRMED' if is_owner else 'UNVERIFIED'
        if kind=='ai_inferences': status='PROBABLE';origin='AI_INFERENCE'
        if is_owner and kind=='facts': origin='OWNER_CONFIRMED_FACT'
        old=self.db.execute("SELECT * FROM brain_items WHERE kind=? AND item_key=? AND scope IN (?, 'canonical') AND knowledge_status!='SUPERSEDED' ORDER BY id DESC",(kind,key,scope)).fetchall()
        supersedes=None
        for row in old:
            if row['value']==dumps(value): continue
            if is_owner and kind!='ai_inferences':
                self.db.execute("UPDATE brain_items SET knowledge_status='SUPERSEDED' WHERE id=?",(row['id'],));supersedes=row['id']
            else:
                status='CONFLICTING'
        return self._item(kind,scope,key,value,status,origin,source,1 if is_owner else .8,item['quote'],supersedes)

    def dependents(self,scope,topic):
        pending=[topic];seen={topic};out=[]
        while pending:
            for r in self.db.execute('SELECT dependent FROM brain_dependencies WHERE scope=? AND prerequisite=?',(scope,pending.pop())):
                if r[0] not in seen: seen.add(r[0]);out.append(r[0]);pending.append(r[0])
        return sorted(out)

    def add_dependency(self,scope,a,b,source):
        if a==b or a in self.dependents(scope,b): raise ValueError('dependency_cycle')
        with self.db:self.db.execute('INSERT OR IGNORE INTO brain_dependencies VALUES (?,?,?,?)',(scope,a,b,source))

    def _packet(self,scope,topic,source,delays,important,overdue=False):
        impacts=self.dependents(scope,topic)
        factors={'impact':2 if important else 0,'urgency':2 if overdue else 0,'confidence':.8,
                 'novelty':1,'owner_relevance':1 if important else 0,'dependency_impact':len(impacts),'repetition':delays}
        level='HIGH' if (delays>=2 and important) or (overdue and impacts) else 'MEDIUM' if delays or overdue else 'LOW'
        if overdue and important and len(impacts)>=2:
            level='CRITICAL'  # Transparent policy; operational risk, not an observed disaster.
        rules=self.db.execute("SELECT value FROM brain_items WHERE kind='owner_rules' AND scope=? AND item_key IN (?, 'general') ORDER BY id DESC LIMIT 1",(scope,topic)).fetchone()
        muted=False
        if rules:
            mode=json.loads(rules[0]);muted=mode=='mute' and level in ('LOW','MEDIUM')
            if mode=='immediate' and (delays or overdue): level='HIGH'
            if mode=='second_delay' and delays>=2:level='HIGH'
        old=self.db.execute('SELECT * FROM brain_packets WHERE scope=? AND topic=?',(scope,topic)).fetchone()
        sources=list(dict.fromkeys((json.loads(old['sources']) if old else [])+[source]))
        history=[{'value':json.loads(r['value']),'source':r['source']} for r in self.db.execute("SELECT value,source FROM brain_items WHERE scope=? AND kind='commitments' AND item_key=? ORDER BY id",(scope,topic))]
        conclusion={'SUBJECT':topic,'WHAT_CHANGED':('Срок истёк; подтверждения выполнения нет' if overdue else f'Зафиксировано переносов: {delays}'),
                    'HISTORY':history,'IMPACT':impacts,'RISK':'Возможна задержка зависимых задач' if impacts else 'Риск нарушения срока' if overdue or delays>=2 else 'Не установлен',
                    'RECOMMENDED_ACTION':'Уточнить статус и согласовать срок; проверить зависимые задачи' if level in ('HIGH','CRITICAL') else 'Наблюдать',
                    'OWNER_DECISION_REQUIRED':level in ('HIGH','CRITICAL'),'SOURCES':sources,'significance':factors,'muted':muted}
        # One mutable packet per issue; source additions alone do not trigger a resend.
        materially_changed=not old or old['level']!=level or json.loads(old['conclusion'])['WHAT_CHANGED']!=conclusion['WHAT_CHANGED']
        revision=(old['revision'] if old else 0)+int(materially_changed)
        state='WAITING_OWNER' if level in ('HIGH','CRITICAL') else 'SILENT' if level=='LOW' or muted else 'DIGEST'
        self.db.execute('''INSERT INTO brain_packets(scope,topic,level,conclusion,sources,decision_required,revision,state)
          VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(scope,topic) DO UPDATE SET level=excluded.level,
          conclusion=excluded.conclusion,sources=excluded.sources,decision_required=excluded.decision_required,
          revision=excluded.revision,state=excluded.state''',(scope,topic,level,dumps(conclusion),dumps(sources),int(level in ('HIGH','CRITICAL')),revision,state))
        if state=='WAITING_OWNER':
            self.db.execute("INSERT OR IGNORE INTO brain_notifications VALUES (?,?,?,'PENDING')",(scope,topic,revision))
            self.db.execute("UPDATE brain_notifications SET state='SUPERSEDED' WHERE scope=? AND topic=? AND revision<? AND state='PENDING'",(scope,topic,revision))

    def _commitment(self,item,scope,source,author,at,is_owner):
        topic=item['key']; action=item.get('action','promise')
        candidates=self.db.execute('SELECT * FROM brain_commitments WHERE scope=? AND topic=?',(scope,topic)).fetchall()
        old=next((r for r in candidates if r['who']==author),None)
        if old is None and len(candidates)==1 and action in ('postpone','complete'): old=candidates[0]
        who=old['who'] if old else author
        due=deadline(item['quote'],at)
        if action=='complete':
            # Only the accountable person or verified owner can confirm completion.
            if old and (author==who or is_owner):
                self.db.execute("UPDATE brain_commitments SET status='DONE',completion_source=? WHERE scope=? AND topic=? AND who=?",(source,scope,topic,who))
            return
        delays=(old['delays'] if old else 0)+int(action=='postpone' and old is not None and due is not None and due['end']!=old['expected_at'])
        important=bool(item.get('important')) or bool(old and old['important'])
        self.db.execute('''INSERT INTO brain_commitments VALUES (?,?,?,?,?,?,?,'OPEN',NULL,?,?,?)
          ON CONFLICT(scope,topic,who) DO UPDATE SET what=excluded.what,
          expected_at=coalesce(excluded.expected_at,brain_commitments.expected_at),
          deadline_json=coalesce(excluded.deadline_json,brain_commitments.deadline_json),
          status='OPEN',source=excluded.source,delays=excluded.delays,important=excluded.important''',
          (scope,topic,who,item['value'],at.isoformat(),due['end'] if due else None,dumps(due) if due else None,source,delays,int(important)))
        self._item('commitments',scope,topic,item['value'],'UNVERIFIED','EXTRACTED_FACT',source,item.get('confidence',.8),item['quote'])
        if due:self._item('deadlines',scope,topic,due,'UNVERIFIED','EXTRACTED_FACT',source,item.get('confidence',.8),item['quote'])
        self._packet(scope,topic,source,delays,important)

    def tick(self,at):
        with self.db:
            rows=self.db.execute("SELECT * FROM brain_commitments WHERE status='OPEN' AND expected_at IS NOT NULL").fetchall()
            for row in rows:
                if datetime.fromisoformat(row['expected_at'])>=at:continue
                self.db.execute("UPDATE brain_commitments SET status='OVERDUE' WHERE scope=? AND topic=? AND who=?",(row['scope'],row['topic'],row['who']))
                self._item('open_loops',row['scope'],row['topic'],{'reason':'no completion evidence','expected_at':row['expected_at']},'PROBABLE','AI_INFERENCE',row['source'],.8,'Derived from recorded deadline, not proof of nonperformance')
                self._packet(row['scope'],row['topic'],row['source'],row['delays'],row['important'],True)

    def process_one(self,now=None):
        now=time.time() if now is None else now
        row=self.db.execute("SELECT * FROM events WHERE state IN ('RECEIVED','EXTRACTED','WAITING_AI') AND next_attempt<=? ORDER BY update_id LIMIT 1",(now,)).fetchone()
        if row is None:return False
        uid=row['update_id'];raw=json.loads(row['raw']);msg=raw.get('message') or raw['edited_message']
        source_type='TELEGRAM_TEXT'
        input_sources=[]
        if row['kind']!='text':
            envelope=json.loads(row['extracted']) if row['extracted'] else {}
            if envelope.get('status')!='EXTRACTED':
                with self.db:self.db.execute("UPDATE events SET state='WAITING_MEDIA',error_code='media_adapter_pending' WHERE update_id=? AND state='RECEIVED'",(uid,))
                return True
            input_sources=media_sources(envelope,msg,'event:'+str(uid))
            text=render_sources(input_sources)
            source_type=envelope.get('source_type','MEDIA')
        else:
            text=msg['text']
            input_sources=[{'channel':'TELEGRAM_TEXT','text':text,'source_ref':'event:'+str(uid)}]
        scope=str(row['chat_id']);author=str(msg.get('from',{}).get('id','unknown'))
        is_owner=row['kind']=='text' and self.owner_id is not None and author==str(self.owner_id)
        at=datetime.fromtimestamp(msg['date'],TZ);source='event:'+str(uid)
        if row['kind']=='text':self.store.transition(uid,'EXTRACTED',extracted=dumps({'text':text,'source':'TELEGRAM_TEXT'}))
        self.store.transition(uid,'WAITING_AI')
        with self.db:self.db.execute("INSERT INTO brain_jobs VALUES (?,'WAITING_AI',0,?) ON CONFLICT(event_id) DO NOTHING",(uid,now))
        topics=[r[0] for r in self.db.execute("SELECT topic FROM brain_commitments WHERE scope=? AND status!='DONE'",(scope,))]
        history=[dict(r) for r in self.db.execute('SELECT kind,item_key,value,knowledge_status,source FROM brain_items WHERE scope=? ORDER BY id DESC LIMIT 30',(scope,))]
        request={'text':text,'at':at,'is_owner':is_owner,'active_topics':topics,'history':history,'sources':input_sources}
        try:
            result=self.provider.analyze(request)
            items=result['items']
            if not isinstance(items,list) or len(items)>50:raise ValueError('invalid_extraction')
            for item in items:
                confidence=item.get('confidence',.8)
                if type(confidence) not in (int,float) or not 0<=confidence<=1:raise ValueError('invalid_confidence')
                if item['kind'] not in KINDS or not isinstance(item['key'],str) or not item['key'] or not isinstance(item['quote'],str) or not item['quote'] or not any(item['quote'] in part['text'] for part in input_sources):raise ValueError('ungrounded_extraction')
                if item['kind']=='owner_rules' and (not is_owner or item['value'] not in ('mute','immediate','second_delay')):raise ValueError('unauthorized_rule')
            result={**result,'input_sources':source_manifest(input_sources),
                    'items':[{**item,'quote_channels':[part['channel'] for part in input_sources if item['quote'] in part['text']]} for item in items]}
            items=result['items']
            with self.db:
                self.db.execute('INSERT OR IGNORE INTO brain_sources VALUES (?,?,?,?,?,?)',(source,uid,source_type,author,at.isoformat(),result.get('method','provider')))
                if not self.db.execute("SELECT 1 FROM brain_items WHERE kind='people' AND scope=? AND item_key=?",(scope,author)).fetchone():
                    self._item('people',scope,author,{'role':None,'responsibility':None},'UNVERIFIED','EXTRACTED_FACT',source,1,'Observed message author')
                for item in items:
                    if item['kind']=='commitments':self._commitment(item,scope,source,author,at,is_owner)
                    else:
                        self._fact(item,scope,source,is_owner)
                        if item['kind']=='open_loops':
                            prior=self.db.execute('SELECT sources FROM brain_decisions WHERE scope=? AND topic=?',(scope,item['key'])).fetchone()
                            refs=list(dict.fromkeys((json.loads(prior[0]) if prior else [])+[source]))
                            self.db.execute("INSERT INTO brain_decisions VALUES (?,?,?,'OPEN',NULL) ON CONFLICT(scope,topic) DO UPDATE SET sources=excluded.sources",(scope,item['key'],dumps(refs)))
                self.db.execute("UPDATE events SET state='ANALYSED',analysis=?,error_code=NULL,updated_at=? WHERE update_id=?",(dumps(result),now,uid))
                self.db.execute("UPDATE brain_jobs SET state='ANALYSED',updated_at=? WHERE event_id=?",(now,uid))
                self.db.execute("INSERT INTO brain_audit(event_id,action,at) VALUES (?,'brain_applied',?)",(uid,now))
            return True
        except Exception as exc:
            n=row['attempts']+1
            self.store.transition(uid,'WAITING_AI',attempts=n,next_attempt=now+min(86400,60*2**min(n,10)),error_code=(getattr(getattr(exc,'state',None),'value',None) or 'brain_provider_or_validation'))
            with self.db:self.db.execute('UPDATE brain_jobs SET attempts=attempts+1,updated_at=? WHERE event_id=?',(now,uid))
            return True

    def explain(self,item_id):
        r=self.db.execute('''SELECT i.*,s.source_type,s.event_id,s.author,s.timestamp,s.method
          FROM brain_items i JOIN brain_sources s ON i.source=s.id WHERE i.id=?''',(item_id,)).fetchone()
        return dict(r) if r else None

    def tower(self):
        # No fabricated project progress; all workstreams start waiting for evidence.
        return {'opening':OPENING.isoformat(),'milestones':{('OPENING DAY' if d==0 else f'D-{d}'):(OPENING-timedelta(days=d)).isoformat() for d in [30,14,7,3,1,0]},
                'workstreams':{k:next((r['state'] for r in self.db.execute('SELECT state FROM brain_workstreams WHERE category=?',(k,))),'WAITING_OWNER') for k in CATEGORIES},'basis':'schedule only; no completion evidence'}

    def accountability(self,scope,who):
        """Observed statuses only, never personality scoring."""
        rows=[dict(r) for r in self.db.execute('SELECT * FROM brain_commitments WHERE scope=? AND who=?',(scope,who))]
        completed_on_time=0
        for row in rows:
            if row['completion_source'] and row['expected_at']:
                stamp=self.db.execute('SELECT timestamp FROM brain_sources WHERE id=?',(row['completion_source'],)).fetchone()
                if stamp and datetime.fromisoformat(stamp[0])<=datetime.fromisoformat(row['expected_at']):completed_on_time+=1
        return {'commitments':rows,'completed_on_time':completed_on_time,
                'overdue_without_evidence':sum(r['status']=='OVERDUE' for r in rows)}

    def record_experiment(self,scope,key,stage,payload,source):
        stages=['IDEA','HYPOTHESIS','TEST','RESULT','LEARNING']
        if stage not in stages:raise ValueError('invalid_experiment_stage')
        previous=self.db.execute("SELECT value FROM brain_items WHERE kind='marketing_experiments' AND scope=? AND item_key=? ORDER BY id DESC LIMIT 1",(scope,key)).fetchone()
        prior=stages.index(json.loads(previous[0])['stage']) if previous else -1
        if stages.index(stage)!=prior+1:raise ValueError('experiment_sequence')
        with self.db:
            return self._item('marketing_experiments',scope,key,{'stage':stage,'data':payload},'UNVERIFIED','EXTRACTED_FACT',source,.8,'Structured experiment input')

    def notification_candidates(self):
        # Preview only. One current packet per issue, no live delivery enabled.
        return [dict(r) for r in self.db.execute('''SELECT p.* FROM brain_packets p
           JOIN brain_notifications n ON n.scope=p.scope AND n.topic=p.topic AND n.revision=p.revision
           WHERE n.state='PENDING' AND p.state='WAITING_OWNER' ''')]

    def set_workstream(self,category,state,source):
        if category not in CATEGORIES or state not in {'DONE','IN_PROGRESS','AT_RISK','BLOCKED','WAITING_OWNER'}:
            raise ValueError('invalid_workstream_state')
        with self.db:self.db.execute('INSERT INTO brain_workstreams VALUES (?,?,?) ON CONFLICT(category) DO UPDATE SET state=excluded.state,source=excluded.source',(category,state,source))

    def resolve_decision(self,scope,topic,source):
        # Only a stored source authored by the configured owner can resolve it.
        src=self.db.execute('SELECT author FROM brain_sources WHERE id=?',(source,)).fetchone()
        if not src or self.owner_id is None or src['author']!=str(self.owner_id):raise ValueError('owner_confirmation_required')
        with self.db:self.db.execute("UPDATE brain_decisions SET state='RESOLVED',resolution_source=? WHERE scope=? AND topic=?",(source,scope,topic))
