"""Local-only report and explicitly mocked benchmark; never calls a paid API."""
import argparse
import json
import os
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from time import sleep
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from backend import operations


def demo():
    from fastapi.testclient import TestClient
    from backend import main, claude_service
    with TemporaryDirectory(prefix='buildflow-operations-') as folder:
        with patch.dict(os.environ, {'BUILDFLOW_OPERATIONS_DB':str(Path(folder)/'demo.sqlite3'),
            'BUILDFLOW_MODEL_PRICING_JSON':json.dumps({'claude-sonnet-5':{
                'input':3,'output':15,'cache_read':.3,'cache_write':3.75}}),
            'BUILDFLOW_ANSWER_TTL_SECONDS':'300', 'BUILDFLOW_ANSWER_CACHE_SIZE':'256'}):
            provider = Mock()
            counter = 0
            def completion(**kwargs):
                nonlocal counter
                counter += 1
                sleep(.025)  # Explicitly simulated provider delay; not a live latency measurement.
                usage = NS(input_tokens=1000,output_tokens=100,cache_read_input_tokens=0,cache_creation_input_tokens=0)
                if counter % 2:
                    return NS(stop_reason='tool_use',content=[NS(type='tool_use', id=f'tool-{counter}',
                        name='get_critical_rfis', input={'project_id':101})], usage=usage)
                return NS(stop_reason='end_turn', content=[NS(type='text',text='Structured RFIs 1 and 3 are critical.')], usage=usage)
            provider.messages.create.side_effect = completion
            with patch.object(claude_service, 'client', provider), patch.object(claude_service, 'load_dotenv', side_effect=AssertionError('No credential files')):
                with TestClient(main.app) as api:
                    with patch.object(operations, 'deterministic_route', return_value=None):
                        for _ in range(10):
                            response = api.post('/ai/chat',json={'message':'Which RFIs are critical?', 'project_id':101})
                            assert response.status_code == 200
                    before = operations.store().events()
                    for index in range(10):
                        question = 'Which RFIs are critical?' if index % 2 == 0 else ' WHICH   RFIs are CRITICAL? '
                        response = api.post('/ai/chat',json={'message':question,'project_id':101})
                        assert response.status_code == 200 and 'Electrical routing conflict' in response.json()['answer']
                    after = operations.store().events()[len(before):]
            return {'label':'MOCKED benchmark; provider delay, token usage, and pricing are illustrative fixtures. No paid requests.',
                    'before':operations.summarize(before), 'after':operations.summarize(after)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('report','demo'))
    parser.add_argument('--db', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        report = demo() if args.command == 'demo' else operations.summarize(
            (operations.Store(args.db) if args.db else operations.store()).events())
        text = json.dumps(report, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text+'\n', encoding='utf-8')
        print(text)
        return 0
    except (OSError, sqlite3.Error):
        print('Local operations report unavailable; check database path and permissions.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
