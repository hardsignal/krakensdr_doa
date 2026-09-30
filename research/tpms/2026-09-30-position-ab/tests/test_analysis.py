"""Regression checks use only temporary files for corruption fixtures."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analyze', HERE / 'analyze.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class ExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((HERE / 'manifest.json').read_text())
        cls.result = analysis.analyze(cls.manifest)
        cls.trials = {t['trial']: t for t in cls.result['trials']}

    def test_known_bearings(self):
        expected = {
            'A001': (5, 279.8, 279, 281, 0.9797958971132712),
            'A003': (4, 277.5, 277, 278, 0.5),
            'A004': (4, 287.25, 285, 288, 1.299038105676658),
            'A005': (4, 291.75, 291, 293, 0.82915619758885),
            'B001': (10, 251.4, 247, 255, 2.2891046284519194),
            'B002': (5, 248.8, 248, 249, 0.4),
            'B003': (5, 249.2, 249, 250, 0.4),
        }
        keys = ['row_count', 'bearing_mean_deg', 'bearing_min_deg',
                'bearing_max_deg', 'bearing_population_std_deg']
        for trial, values in expected.items():
            for key, value in zip(keys, values):
                with self.subTest(trial=trial, key=key):
                    self.assertAlmostEqual(self.trials[trial][key], value)

    def test_null_is_preserved(self):
        trial = self.trials['A002']
        self.assertTrue(trial['null_capture'])
        self.assertEqual(trial['row_count'], 0)
        for key in ['bearing_mean_deg', 'bearing_min_deg', 'bearing_max_deg',
                    'bearing_population_std_deg', 'confidence_mean', 'power_mean']:
            self.assertIsNone(trial[key])
        source = next(s for s in self.manifest['sources'] if s.get('trial') == 'A002')
        self.assertEqual((HERE / source['path']).read_bytes(), b'')
        self.assertEqual(source['sha256'], 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')

    def test_position_a_success_rate(self):
        self.assertEqual(self.result['position_a'], {
            'attempts': 5, 'successful_captures': 4, 'successful_capture_rate': 0.8,
            'successful_rows': 17, 'bearing_min_deg': 277, 'bearing_max_deg': 293})

    def test_b001_is_supplementary(self):
        self.assertEqual(self.result['position_b_primary']['trials'], ['B002', 'B003'])
        self.assertEqual(self.result['position_b_supplementary'], ['B001'])
        self.assertEqual(self.trials['B001']['activations'], 2)
        self.assertEqual(self.trials['B001']['role'], 'supplementary_two_activations')
        self.assertAlmostEqual(self.result['position_b_primary']['absolute_trial_mean_difference_deg'], 0.4)
        bad = copy.deepcopy(self.manifest)
        next(s for s in bad['sources'] if s.get('trial') == 'B001')['activations'] = 1
        with self.assertRaisesRegex(ValueError, 'B001 must remain supplementary'):
            analysis.analyze(bad)

    def test_all_source_hashes_and_existing_evidence(self):
        self.assertEqual(len(self.manifest['sources']), 15)
        self.assertEqual(sum(s['kind'] == 'raw_capture' for s in self.manifest['sources']), 8)
        self.assertEqual(sum('recorded_sha256' in s for s in self.manifest['sources']), 5)
        analysis.verify_sources(self.manifest)

    def test_hash_mismatch_is_fatal(self):
        bad = copy.deepcopy(self.manifest)
        bad['sources'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            analysis.analyze(bad)

    def test_malformed_csv(self):
        source = next(s for s in self.manifest['sources'] if s.get('trial') == 'B002')
        valid = (HERE / source['path']).read_text().splitlines()[0]
        fields = valid.split(',')
        cases = ['1,2,3\n', '\n', '"unterminated\n', valid + ',extra\n']
        for index, value in [(1, 'nan'), (1, '361'), (2, 'bad'), (3, 'inf'),
                             (4, '123'), (17, 'oops'), (376, '')]:
            row = fields.copy()
            row[index] = value
            cases.append(','.join(row) + '\n')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'malformed.csv'
            for content in cases:
                with self.subTest(content=content[:50]):
                    path.write_text(content)
                    with self.assertRaisesRegex(ValueError, 'line 1: malformed CSV'):
                        analysis.read_capture(path)

    def test_confidence_power_and_population_std(self):
        result = analysis.summarize([(10, 2, -30), (14, 4, -20)])
        self.assertEqual(result['confidence_mean'], 3)
        self.assertEqual(result['power_mean'], -25)
        self.assertEqual(result['bearing_population_std_deg'], 2)
        self.assertAlmostEqual(self.trials['B002']['confidence_mean'], 3.6234530806541443)
        self.assertAlmostEqual(self.trials['B002']['power_mean'], -24.92818603515625)

    def test_deterministic_cli_and_derived_snapshot(self):
        command = [sys.executable, str(HERE / 'analyze.py')]
        first = subprocess.check_output(command, cwd='/tmp')
        self.assertEqual(first, subprocess.check_output(command, cwd='/tmp'))
        self.assertIn(b'NULL', first)
        self.assertIn(b'TWO activations', first)
        snapshot = subprocess.check_output(command + ['--json'], cwd='/tmp')
        self.assertEqual(snapshot, (HERE / 'statistics.json').read_bytes())
        self.assertEqual(json.loads(snapshot), self.result)


if __name__ == '__main__':
    unittest.main()
