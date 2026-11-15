"""Local deterministic routing, bounded cache, and sanitized request measurements."""
import re
import hashlib
import json
import logging
import math
import os
import sqlite3
import time
import uuid
from contextlib import closing, contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

from backend import project_service

CURRENT = ContextVar('buildflow_request', default=None)
LOGGER = logging.getLogger('buildflow.operations')
VERSION = 'deterministic-v1-validation-v1'


def setting(name, default, maximum):
    try:
        return max(0, min(int(os.environ.get(name, default)), maximum))
    except ValueError:
        return default


def store():
    return Store(Path(os.environ.get('BUILDFLOW_OPERATIONS_DB', Path(__file__).resolve().parents[1] / '.cache' / 'operations.sqlite3')))


class Store:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10)) as conn, conn:
            conn.execute('BEGIN IMMEDIATE')
            conn.execute('CREATE TABLE IF NOT EXISTS answer_cache (key TEXT PRIMARY KEY, answer TEXT NOT NULL, expires REAL, created REAL)')
            conn.execute('CREATE TABLE IF NOT EXISTS request_events (id INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
            yield conn

    def get(self, key, now=None):
        with self.connection() as conn:
            row = conn.execute('SELECT answer FROM answer_cache WHERE key=? AND expires>?', (key, time.time() if now is None else now)).fetchone()
            return row[0] if row else None

    def put(self, key, answer, ttl, maximum, now=None):
        if ttl <= 0 or maximum <= 0:
            return
        now = time.time() if now is None else now
        with self.connection() as conn:
            conn.execute('DELETE FROM answer_cache WHERE expires<=?', (now,))
            conn.execute('INSERT OR REPLACE INTO answer_cache VALUES (?,?,?,?)', (key, answer, now+ttl, now))
            conn.execute('DELETE FROM answer_cache WHERE key NOT IN (SELECT key FROM answer_cache ORDER BY created DESC, key DESC LIMIT ?)', (maximum,))

    def cache_size(self):
        with self.connection() as conn:
            return conn.execute('SELECT COUNT(*) FROM answer_cache').fetchone()[0]

    def record(self, event):
        with self.connection() as conn:
            conn.execute('INSERT INTO request_events(payload) VALUES (?)', (json.dumps(event),))
            conn.execute('DELETE FROM request_events WHERE id NOT IN (SELECT id FROM request_events ORDER BY id DESC LIMIT 10000)')

    def events(self):
        with self.connection() as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT payload FROM request_events ORDER BY id')]


def cache_identity(question, project_id, route, project):
    identity = {'question':normalize(question), 'project_id':project_id, 'route':route,
        'data':project, 'validation_version':VERSION, 'documents':'not-used', 'model':'none', 'prompt':'none',
        'business_code':hashlib.sha256(Path(project_service.__file__).read_bytes()).hexdigest()}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def metric(**values):
    event = CURRENT.get()
    if event is not None:
        event.update(values)


def increment(field, amount=1):
    event = CURRENT.get()
    if event is not None:
        event[field] = event.get(field, 0) + amount


def begin():
    return CURRENT.set({'request_id':uuid.uuid4().hex, 'timestamp':datetime.now(timezone.utc).isoformat(),
        'project_id':None, 'selected_project_id':None, 'route':'validation', 'cache':'bypass', 'outcome':'ok', 'claude_calls':0,
        'tool_calls':0, 'retrieval_ms':0, 'rerank_ms':0, 'claude_ms':0, 'calls':[]})


def finish(token, started, status):
    event = CURRENT.get()
    event['latency_ms'] = round((time.perf_counter()-started)*1000, 3)
    if status >= 400:
        event['outcome'] = {422:'invalid_request',404:'project_not_found',429:'rate_limited',
                            502:'provider_response_error',503:'service_unavailable',504:'timeout'}.get(status, 'request_error')
    costs = [call['estimated_usd'] for call in event['calls']]
    event['estimated_usd'] = sum(costs) if all(cost is not None for cost in costs) else None
    try:
        LOGGER.info(json.dumps(event))
        store().record(event)
    except (OSError, sqlite3.Error):
        LOGGER.warning('operations_storage_unavailable')
    finally:
        CURRENT.reset(token)


def usage_record(model, usage, latency_ms):
    def count(obj, field):
        value = getattr(obj, field, None)
        return value if type(value) is int and value >= 0 else None
    result = {'model':model if isinstance(model, str) and re.fullmatch(r'[\w.-]{1,100}', model) else 'unknown',
              'latency_ms':round(latency_ms, 3)}
    for field in ('input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens'):
        result[field] = count(usage, field)
    details = getattr(usage, 'cache_creation', None)
    five = count(details, 'ephemeral_5m_input_tokens')
    hour = count(details, 'ephemeral_1h_input_tokens')
    result.update(cache_write_5m_tokens=five, cache_write_1h_tokens=hour, estimated_usd=None)
    try:
        rates = json.loads(os.environ.get('BUILDFLOW_MODEL_PRICING_JSON', '{}')).get(model, {})
        categories = {'input':result['input_tokens'], 'output':result['output_tokens'],
                      'cache_read':result['cache_read_input_tokens'] or 0}
        total = result['cache_creation_input_tokens'] or 0
        if five is not None and hour is not None:
            categories.update(cache_write_5m=five, cache_write_1h=hour)
            if total != five + hour:
                return result
        else:
            categories['cache_write'] = total
        cost = 0
        for category, tokens in categories.items():
            if tokens is None:
                return result
            if tokens:
                rate = rates.get(category)
                if type(rate) not in (int, float) or not math.isfinite(rate) or rate < 0:
                    return result
                cost += tokens * rate / 1_000_000
        result['estimated_usd'] = cost if math.isfinite(cost) else None
    except (ValueError, TypeError, AttributeError):
        pass
    return result


def provider_call(model, invoke):
    started = time.perf_counter()
    response = None
    increment('claude_calls')
    try:
        response = invoke()
        return response
    finally:
        elapsed = (time.perf_counter()-started)*1000
        increment('claude_ms', elapsed)
        event = CURRENT.get()
        if event is not None:
            event['calls'].append(usage_record(model, getattr(response, 'usage', None), elapsed))


def cached_deterministic(question, project_id, route):
    from copy import deepcopy
    project = deepcopy(project_service.get_project_by_id(project_id))
    key = cache_identity(question, project_id, route, project)
    metric(route='deterministic:' + route, cache='miss', project_id=project_id)
    ttl = setting('BUILDFLOW_ANSWER_TTL_SECONDS', 300, 86400)
    maximum = setting('BUILDFLOW_ANSWER_CACHE_SIZE', 256, 5000)
    if not ttl or not maximum:
        metric(cache='disabled')
    key = hashlib.sha256(f'{key}:{ttl}:{maximum}'.encode()).hexdigest()
    try:
        answer = store().get(key) if ttl and maximum else None
        if answer is not None:
            metric(cache='hit')
            return answer
    except (OSError, sqlite3.Error):
        metric(cache='unavailable')
    answer = deterministic_answer(route, project)
    try:
        store().put(key, answer, ttl, maximum)
    except (OSError, sqlite3.Error):
        metric(cache='unavailable')
    return answer


def summarize(events):
    from collections import Counter
    import statistics
    calls = [call for event in events for call in event['calls']]
    hits = sum(event['cache'] == 'hit' for event in events)
    misses = sum(event['cache'] == 'miss' for event in events)
    latencies = sorted(event['latency_ms'] for event in events)
    no_generation = sum(event['route'].startswith('deterministic:') and event['claude_calls'] == 0 for event in events)
    known = [call['estimated_usd'] for call in calls if call['estimated_usd'] is not None]
    return {'requests':len(events), 'routes':dict(Counter(e['route'] for e in events)),
        'outcomes':dict(Counter(e['outcome'] for e in events)), 'answer_cache_hits':hits,
        'answer_cache_hit_rate_eligible':hits/(hits+misses) if hits+misses else None,
        'claude_calls':sum(e['claude_calls'] for e in events),
        'deterministic_requests_without_generation':no_generation,
        'avoided_calls_vs_simulated_two_call_baseline':no_generation*2,
        'median_request_ms':round(statistics.median(latencies), 3) if latencies else None,
        'p95_request_ms':latencies[min(len(latencies)-1, int(len(latencies)*.95))] if latencies else None,
        'total_claude_ms':round(sum(e['claude_ms'] for e in events), 3),
        'total_retrieval_ms':round(sum(e['retrieval_ms'] for e in events), 3),
        'total_rerank_ms':round(sum(e['rerank_ms'] for e in events), 3),
        'tool_calls':sum(e['tool_calls'] for e in events),
        'reported_tokens':{field:sum(call[field] or 0 for call in calls) for field in
            ('input_tokens','output_tokens','cache_read_input_tokens','cache_creation_input_tokens')},
        'calls_without_complete_usage':sum(c['input_tokens'] is None or c['output_tokens'] is None for c in calls),
        'estimated_api_spend_usd':round(sum(known), 10) if len(known) == len(calls) else None,
        'priced_call_subtotal_usd':round(sum(known), 10), 'unpriced_calls':len(calls)-len(known),
        'note':'USD values are configurable API estimates, not invoices. Local compute/infrastructure costs excluded. '
               'Avoided-call count uses a simulated two-call baseline, not measured billing savings. '
               'Answer caching and provider prompt-cache token counters are distinct.'}


def normalize(question):
    return ' '.join(question.lower().split())


def deterministic_route(question):
    question = normalize(question)
    patterns = {
        'total': r'how many rfis are open',
        'critical': r'which rfis are critical',
        'blocking': r'how many rfis are blocking',
        'counts': r'give me the project rfi counts',
    }
    for route, pattern in patterns.items():
        if re.fullmatch(pattern + r'(?: for project \d+)?[?.]?', question):
            return route
    return None


def deterministic_answer(route, project):
    summary = project_service.get_project_summary(project)
    heading = f"**{project['name']} — structured sample data**\n\n"
    if route == 'critical':
        rfis = project_service.get_critical_rfis(project['rfis'])
        return heading + ('\n'.join(f"- RFI {r['id']}: {r['title']} — blocking, {r['days_open']} days open." for r in rfis)
                          or 'No critical RFIs.')
    if route == 'blocking':
        return heading + f"**{summary['blocking_rfis']} blocking RFIs.**"
    if route == 'total':
        return heading + f"**{summary['total_rfis']} RFIs in the sample register.** The sample has no separate closed-status field."
    return heading + f"**{summary['total_rfis']} total RFIs · {summary['critical_rfis']} critical · {summary['blocking_rfis']} blocking.**"
