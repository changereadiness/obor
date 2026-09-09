import json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / 'scripts'
FIX = Path(__file__).parent / 'fixtures'
SOURCE = 'National Bureau of Statistics of China — Latest Releases'

CASES = [
    {
        'id':'raw-price','url':'https://example.test/nbs/prices','title':'Market Prices of Important Means of Production in Circulation, August 1-10, 2026',
        'published_at':'2026-08-14','fixture':'production_inputs.html','expected':'China production-input prices mostly declined'
    },
    {
        'id':'raw-retail','url':'https://example.test/nbs/retail','title':'Total Retail Sales of Consumer Goods from January to July 2026',
        'published_at':'2026-08-18','fixture':'retail_sales.html','expected':'China retail sales grew 0.6%'
    },
    {
        'id':'raw-industrial','url':'https://example.test/nbs/industrial','title':'Industrial Production Operation in July 2026',
        'published_at':'2026-08-18','fixture':'industrial_production.html','expected':'China industrial output grew 4.5%'
    },
]


def raw_item(c):
    return {
        'id':c['id'],'url':c['url'],'title':c['title'],'description':c['title'],
        'published_at':c['published_at'],'source':SOURCE,'source_type':'Primary source'
    }


def existing_signal(c):
    slug=c['id']
    return {
        'id':'sig-'+c['id'],'title':c['title'],'slug':slug,'published_at':c['published_at'],
        'event_date':c['published_at'],'source':SOURCE,'source_url':c['url'],'source_type':'Primary source',
        'summary':'Previously published verified signal retained for clean-engine reprocessing.',
        'what_happened':'Legacy placeholder factual summary pending clean reprocessing.',
        'canadian_relevance':'Previously published Canadian relevance placeholder pending clean reprocessing.',
        'opportunity_or_risk':'WATCH','relevance_score':70,'confidence_score':70,
        'sectors':['Other'],'categories':['Markets'],'direction':'Global → Canada/China',
        'entities':['China'],'related_signals':[],'status':'published','synthesis_version':17
    }


class V17IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'data/raw').mkdir(parents=True)
        (self.root/'signals').mkdir()
        (self.root/'data/raw/items.json').write_text(json.dumps([raw_item(c) for c in CASES], indent=2))
        (self.root/'data/signals.json').write_text(json.dumps([existing_signal(c) for c in CASES], indent=2))
        (self.root/'data/overrides.json').write_text('{}')
        fmap={c['url']:str(FIX/c['fixture']) for c in CASES}
        self.mapfile=self.root/'fixture-map.json'; self.mapfile.write_text(json.dumps(fmap))
        self.env=os.environ.copy(); self.env['OBOR_ROOT']=str(self.root); self.env['OBOR_SOURCE_FIXTURE_MAP']=str(self.mapfile)
        self.ingest_fixture=self.root/'ingest-items.json'; self.ingest_fixture.write_text(json.dumps([raw_item(c) for c in CASES], indent=2))
        self.env['OBOR_INGEST_FIXTURE_ITEMS']=str(self.ingest_fixture)
        # Preserve one explicit demo page to prove recovery does not admit it.
        demo=self.root/'signals/demo-record/index.html'; demo.parent.mkdir(parents=True)
        demo.write_text('<h1>Illustrative signal: demo</h1><p class="eyebrow">SOURCE</p><p>Illustrative / demo content · <a href="https://example.test/demo">View source →</a></p>')

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, name):
        p=subprocess.run([sys.executable,str(SCRIPTS/name)],cwd=REPO,env=self.env,text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stdout+'\n'+p.stderr)
        return p.stdout

    def assert_clean_outputs(self):
        signals=json.loads((self.root/'data/signals.json').read_text())
        self.assertEqual(len(signals),3)
        by_url={s['source_url']:s for s in signals}
        for c in CASES:
            s=by_url[c['url']]
            self.assertIn(c['expected'],s['title'])
            self.assertEqual(s['synthesis_version'],'clean-m5')
            self.assertEqual(s['clean_analysis']['status'],'ready')
            self.assertIsInstance(s['what_happened'],list)
            self.assertGreaterEqual(len(s['what_happened']),1)
        blob=json.dumps(signals)
        for bad in ['1685797%','98677%','39022%','287744%','economic price movement','factory demand']:
            self.assertNotIn(bad,blob)
        return signals

    def test_full_v17_style_pipeline_build_and_gate(self):
        out=self.run_script('pipeline.py')
        self.assertIn('updated_existing=3',out)
        self.assert_clean_outputs()
        self.run_script('build.py')
        gate=self.run_script('validate.py')
        self.assertIn('Quality gate passed: 3 signals',gate)
        pages=' '.join(p.read_text() for p in (self.root/'signals').glob('*/index.html'))
        self.assertIn('China retail sales grew 0.6%',pages)
        self.assertIn('<p class="eyebrow">WHAT HAPPENED</p><ul><li>',pages)
        self.assertNotIn('39022%',pages)

    def test_run_py_orchestrates_fixture_ingest_pipeline_and_build(self):
        # Remove the pre-seeded raw file: run.py must recreate it through ingest.py.
        (self.root/'data/raw/items.json').unlink()
        out=self.run_script('run.py')
        self.assertIn('Collection state: fixture',out)
        self.assertIn('updated_existing=3',out)
        self.assert_clean_outputs()
        gate=self.run_script('validate.py')
        self.assertIn('Quality gate passed: 3 signals',gate)


    def test_recovery_from_generated_pages_then_clean_reprocess(self):
        self.run_script('pipeline.py')
        self.run_script('build.py')
        # Simulate loss/reversion of the canonical ledger while pages survive.
        (self.root/'data/signals.json').write_text('[]')
        out=self.run_script('pipeline.py')
        self.assertIn('updated_existing=3',out)
        self.assert_clean_outputs()
        self.run_script('build.py')
        self.run_script('validate.py')


if __name__=='__main__':
    unittest.main()
