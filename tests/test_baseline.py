"""The baseline checker against a small fixture region (no network). Run: python3 -m unittest tests.test_baseline"""
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import baseline  # noqa: E402

SRC = [{'outlet': 'Example', 'date': '2026-08-24', 'url': 'https://example.org/a'}]


def write(root: Path, name: str, rows):
    (root / 'xx').mkdir(parents=True, exist_ok=True)
    (root / 'xx' / name).write_text(json.dumps(rows, ensure_ascii=False))


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        write(root, 'promises.json', [{'id': 'lpg', 'party': 'TVK', 'promise': 'Six free LPG cylinders a year', 'promised': '6',
                                       'current': '3 a year from Jan 2027', 'verdict': 'started', 'status': 'verified',
                                       'sources': SRC, 'as_of': '2026-11-10', 'keywords': ['lpg', 'cylinder', 'சிலிண்டர்', 'tvk']}])
        write(root, 'facts.json', [{'id': 'conclave', 'topic': 'deals', 'statement': '97 MoUs were signed on 13 Aug.', 'value': '67452',
                                    'alt_values': ['67542'], 'status': 'disputed', 'sources': SRC, 'as_of': '2026-11-10',
                                    'keywords': ['conclave', 'mou', 'tvk']},
                                   {'id': 'steps', 'topic': 'economy', 'statement': 'x', 'status': 'verified', 'sources': SRC,
                                    'as_of': '2026-11-10', 'keywords': ['eps']}])
        write(root, 'watch.json', [{'id': 'speaker', 'when': '2026-12-13', 'what': 'Speaker rules', 'why': 'majority', 'status': 'verified',
                                    'sources': SRC, 'as_of': '2026-11-10', 'keywords': ['speaker', 'disqualification']}])
        write(root, 'rules.json', [{'id': 'no-x', 'all': ['karur'], 'any': ['conspiracy'], 'why': 'probe pending', 'scan_baseline': False}])
        (root / 'xx' / 'log.jsonl').write_text('')
        self.patch = mock.patch.object(baseline, 'ROOT', root)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_check_finds_context_and_flags_status(self):
        out, code = baseline.check('TVK govt to give free cylinders; conclave MoUs reviewed', 'xx')
        self.assertEqual(code, 0)
        self.assertIn('now: 3 a year from Jan 2027', out)
        self.assertIn('Other figures: 67542', out)
        self.assertIn('disputed', out.split('Handle with care')[1])

    def test_generic_words_alone_match_nothing_and_latin_is_whole_word(self):
        out, _ = baseline.check('TVK leader takes three steps forward', 'xx')      # 'tvk' is generic; 'eps' is inside 'steps'
        self.assertIn('Nothing in the baseline matches', out)
        out, _ = baseline.check('சிலிண்டர் விலை', 'xx')
        self.assertIn('LPG', out)

    def test_rule_stops_publication(self):
        out, code = baseline.check('DMK conspiracy behind Karur, says leader', 'xx')
        self.assertEqual(code, 2)
        self.assertTrue(out.startswith('STOP'))

    def test_log_is_shown_next_time(self):
        with self.assertRaises(SystemExit):
            baseline.add_log('xx', 'note', 'http://insecure.example', [], [])
        baseline.add_log('xx', 'Speaker rejected the petition', 'https://example.org/b', ['speaker'], ['speaker'])
        out, _ = baseline.check('What the Speaker did on disqualification', 'xx')
        self.assertIn('Speaker rejected the petition', out)

    def test_due_and_validate(self):
        self.assertTrue(baseline.due('xx', date(2026, 12, 20))[0].startswith('OVERDUE'))
        write(baseline.ROOT, 'watch_more.json', [{'id': 'fy', 'when': 'budget for 2026-27', 'what': 'x', 'why': 'y', 'status': 'verified', 'sources': SRC, 'as_of': '2026-11-10', 'keywords': ['budget']}])
        self.assertTrue(any(l.startswith('undated') for l in baseline.due('xx', date(2026, 12, 20))))
        self.assertEqual(baseline.validate('xx'), [])
        root = baseline.ROOT
        write(root, 'ledger.json', [{'id': 'Bad Id', 'party': 'X', 'status': 'alleged', 'sources': [{'url': 'http://x'}], 'as_of': 'soon', 'keywords': []}])
        errs = ' '.join(baseline.validate('xx'))
        for needle in ('bad id', 'https urls', 'need a response', 'no keywords', 'as_of'):
            self.assertIn(needle, errs)

    def test_real_tn_baseline_is_valid_when_present(self):
        self.patch.stop()
        try:
            if any((baseline.ROOT / 'tn').glob('*.json')):
                self.assertEqual(baseline.validate('tn'), [])
        finally:
            self.patch.start()


if __name__ == '__main__':
    unittest.main()
