import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / 'scripts'

spec = importlib.util.spec_from_file_location('prelaunch_health', SCRIPTS / 'prelaunch_health.py')
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


class PrelaunchHealthTests(unittest.TestCase):
    def test_reference_period_inference_is_explicitly_not_publication_date(self):
        self.assertEqual(
            health.reference_date_from_title('Market Prices, August 21-31, 2026').date().isoformat(),
            '2026-08-31',
        )
        self.assertEqual(
            health.reference_date_from_title('Total Retail Sales from January to July 2026').date().isoformat(),
            '2026-07-31',
        )
        self.assertEqual(
            health.reference_date_from_title('Consumer Price Index in August 2026').date().isoformat(),
            '2026-08-31',
        )

    def test_ingest_fixture_preserves_first_seen_and_reports_true_discovery(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'data/raw').mkdir(parents=True)
            items = [{
                'id': 'raw-1', 'title': 'China industrial production in August 2026',
                'url': 'https://example.test/1', 'description': '', 'published_at': '2026-09-01T00:00:00+00:00',
                'source': 'Fixture Source', 'source_type': 'Primary source', 'country': 'China',
            }]
            fixture = root / 'fixture.json'
            fixture.write_text(json.dumps(items))
            env = os.environ.copy()
            env['OBOR_ROOT'] = str(root)
            env['OBOR_INGEST_FIXTURE_ITEMS'] = str(fixture)

            first = subprocess.run([sys.executable, str(SCRIPTS/'ingest.py')], env=env, text=True, capture_output=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            log1 = json.loads((root/'data/raw/ingest_log.json').read_text())
            stored1 = json.loads((root/'data/raw/items.json').read_text())[0]
            self.assertEqual(log1['items_discovered'], 1)
            self.assertEqual(log1['items_fetched'], 1)
            first_seen = stored1['first_seen_at']

            second = subprocess.run([sys.executable, str(SCRIPTS/'ingest.py')], env=env, text=True, capture_output=True)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            log2 = json.loads((root/'data/raw/ingest_log.json').read_text())
            stored2 = json.loads((root/'data/raw/items.json').read_text())[0]
            self.assertEqual(log2['items_discovered'], 0)
            self.assertEqual(log2['items_fetched'], 1)
            self.assertEqual(stored2['first_seen_at'], first_seen)
            self.assertTrue(stored2['last_seen_at'])

    def test_health_report_separates_degradation_freshness_and_gate_reasons(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root/'data/raw').mkdir(parents=True)
            (root/'data/sources.json').write_text(json.dumps([
                {'name':'NBS','enabled':True}, {'name':'WTO','enabled':True}
            ]))
            (root/'data/raw/ingest_log.json').write_text(json.dumps({
                'collected_at':'2026-09-12T07:00:00+00:00','state':'degraded',
                'sources_enabled':2,'sources_succeeded':1,'items_fetched':1,'items_discovered':0,'items_cached':1,
                'health':[
                    {'source':'NBS','status':'ok','items':1,'method':'html','consecutive_failures':0,'last_success_at':'2026-09-12T07:00:00+00:00'},
                    {'source':'WTO','status':'error','items':0,'consecutive_failures':3,'last_success_at':None,'error':'failed'},
                ]
            }))
            (root/'data/raw/items.json').write_text(json.dumps([{
                'id':'raw-1','title':'Consumer Price Index in August 2026','source':'NBS',
                'published_at':None,'first_seen_at':'2026-09-12T07:00:00+00:00','collected_at':'2026-09-12T07:00:00+00:00'
            }]))
            (root/'data/raw/candidates.json').write_text(json.dumps([
                {'synthesis_status':'evidence_available'}, {'synthesis_status':'insufficient_evidence'}
            ]))
            (root/'data/raw/screening_summary.json').write_text(json.dumps({'raw':1,'screened':1,'candidates':1,'rejected':0}))
            (root/'data/raw/publication_gate.json').write_text(json.dumps({'counts':{'unsupported_sector_no_canada_evidence':1}}))
            (root/'data/signals.json').write_text('[]')
            env = os.environ.copy(); env['OBOR_ROOT'] = str(root)
            p = subprocess.run([sys.executable, str(SCRIPTS/'prelaunch_health.py')], env=env, text=True, capture_output=True)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            report = json.loads((root/'data/raw/prelaunch_health.json').read_text())
            self.assertEqual(report['source_status_counts']['ok'], 1)
            self.assertEqual(report['source_status_counts']['error'], 1)
            by_source = {x['source']:x for x in report['sources']}
            self.assertEqual(by_source['WTO']['consecutive_failures'], 3)
            self.assertEqual(by_source['NBS']['newest_reference_date'], '2026-08-31')
            self.assertEqual(report['publication_gate_counts']['unsupported_sector_no_canada_evidence'], 1)


if __name__ == '__main__':
    unittest.main()
