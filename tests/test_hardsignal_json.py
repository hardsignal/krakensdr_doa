"""Exercise the actual exporter without importing/starting Kraken hardware."""
import ast
import copy
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = '_sdr/_signal_processing/kraken_sdr_signal_processor.py'
BASE_COMMIT = '86528c0273c93baa8fce8a3e5429ad9c6a937141'
SOURCE = (ROOT / RELATIVE).read_text()
TREE = ast.parse(SOURCE)
CLASS = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'SignalProcessor')
METHOD = next(n for n in CLASS.body if isinstance(n, ast.FunctionDef) and n.name == 'wr_hardsignal_json')
RUN = next(n for n in CLASS.body if isinstance(n, ast.FunctionDef) and n.name == 'run')


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.folder = Path(self.directory.name)
        self.target = self.folder / 'hardsignal_live.json'
        self.previous = b'{"previous": true}\n'
        self.target.write_bytes(self.previous)
        self.namespace = dict(np=np, os=os, tempfile=tempfile, json=json, shared_path=str(self.folder))
        module = ast.Module(body=[copy.deepcopy(METHOD)], type_ignores=[])
        exec(compile(module, str(ROOT / RELATIVE), 'exec'), self.namespace)
        self.processor = SimpleNamespace(
            timestamp=np.uint64(1790807003747), theta_0_list=[np.float64(81)],
            freq_list=[np.int64(433868160)], confidence_list=[np.float64(3.125)],
            max_power_level_list=[np.float64(-24.75)], snrs=[np.float64(12.5)],
            number_of_correlated_sources=[np.int64(2)],
            doa_result_log_list=[np.array([-4., -1., 2.])], logger=Mock(),
        )

    def publish(self):
        self.namespace['wr_hardsignal_json'](self.processor)

    def assert_preserved(self):
        self.assertEqual(self.target.read_bytes(), self.previous)
        self.processor.logger.warning.assert_called()

    def assert_clean(self):
        self.assertEqual(list(self.folder.glob('.hardsignal_live.*.tmp')), [])

    def test_payload_types_mapping_and_offset(self):
        self.publish()
        data = json.loads(self.target.read_text())
        self.assertEqual(data, {
            'tStamp': 1790807003747, 'freq': 433868160, 'resultIndex': 0,
            'bearingConvention': 'csv_app_360_minus_theta_0_deg',
            'radioBearing': 279., 'conf': 3.125, 'power': -24.75,
            'snr_db': 12.5, 'num_corr_sources': 2, 'doaArray': [0., 3., 6.],
        })
        for key, value in data.items():
            if key not in ('bearingConvention', 'doaArray'):
                self.assertIn(type(value), (int, float))
        self.assertTrue(all(type(value) is float for value in data['doaArray']))
        self.processor.logger.warning.assert_not_called()
        self.assert_clean()

    def test_bearing_zero_is_360(self):
        self.processor.theta_0_list = [0.]
        self.publish()
        self.assertEqual(json.loads(self.target.read_text())['radioBearing'], 360.)

    def test_only_first_result_exported(self):
        for name in ('theta_0_list', 'freq_list', 'confidence_list', 'max_power_level_list',
                     'snrs', 'number_of_correlated_sources', 'doa_result_log_list'):
            values = getattr(self.processor, name)
            values.append(values[0] + 1)
        self.publish()
        self.assertEqual(json.loads(self.target.read_text())['radioBearing'], 279.)
        self.assertEqual(json.loads(self.target.read_text())['resultIndex'], 0)

    def test_empty_and_misaligned_lists(self):
        names = ('theta_0_list', 'freq_list', 'confidence_list', 'max_power_level_list',
                 'snrs', 'number_of_correlated_sources', 'doa_result_log_list')
        for name in names:
            with self.subTest(name=name):
                values = getattr(self.processor, name)
                setattr(self.processor, name, [])
                self.publish()
                self.assert_preserved()
                self.assert_clean()
                setattr(self.processor, name, values)
        self.processor.snrs.append(99.)
        self.publish()
        self.assert_preserved()

    def test_nonfinite_values(self):
        for name in ('theta_0_list', 'freq_list', 'confidence_list', 'max_power_level_list',
                     'snrs', 'number_of_correlated_sources', 'doa_result_log_list'):
            for invalid in (float('nan'), float('inf'), -float('inf')):
                with self.subTest(name=name, invalid=invalid):
                    values = getattr(self.processor, name)
                    setattr(self.processor, name, [np.array([invalid])] if name == 'doa_result_log_list' else [invalid])
                    self.publish()
                    self.assert_preserved()
                    self.assert_clean()
                    setattr(self.processor, name, values)

    def test_tempfile_creation_failure(self):
        with patch.object(tempfile, 'NamedTemporaryFile', side_effect=PermissionError('denied')):
            self.publish()
        self.assert_preserved()
        self.assert_clean()

    def test_serialization_failure(self):
        def fail(data, output, **kwargs):
            self.assertIs(kwargs['allow_nan'], False)
            output.write('{"partial":')
            raise TypeError('injected serialization failure')
        with patch.object(json, 'dump', side_effect=fail):
            self.publish()
        self.assert_preserved()
        self.assert_clean()

    def test_replace_failure(self):
        with patch.object(os, 'replace', side_effect=OSError('injected replace failure')):
            self.publish()
        self.assert_preserved()
        self.assert_clean()

    def test_cleanup_failure_contained(self):
        with patch.object(os, 'replace', side_effect=OSError('replace failed')):
            with patch.object(os, 'unlink', side_effect=PermissionError('cleanup failed')):
                self.publish()
        self.assert_preserved()
        self.assertEqual(len(list(self.folder.glob('.hardsignal_live.*.tmp'))), 1)
        self.assertEqual(self.processor.logger.warning.call_count, 2)

    def test_atomic_publication_and_actual_mode(self):
        real_replace = os.replace
        real_temporary_file = tempfile.NamedTemporaryFile
        opened = []
        def create(**kwargs):
            output = real_temporary_file(**kwargs)
            opened.append(output)
            return output
        def replace(source, target):
            self.assertTrue(opened[0].closed)
            self.assertEqual(Path(source).parent, self.folder)
            self.assertEqual(self.target.read_bytes(), self.previous)
            self.assertEqual(stat.S_IMODE(Path(source).stat().st_mode), 0o600)
            self.assertEqual(json.loads(Path(source).read_text())['radioBearing'], 279.)
            real_replace(source, target)
        self.target.chmod(0o644)
        with patch.object(tempfile, 'NamedTemporaryFile', side_effect=create):
            with patch.object(os, 'replace', side_effect=replace) as mocked:
                self.publish()
        mocked.assert_called_once()
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode), 0o600)
        self.assertEqual(self.target.stat().st_uid, os.geteuid())
        self.assertTrue(os.access(self.target, os.R_OK))
        self.assert_clean()

    def test_no_existing_file_on_failure(self):
        self.target.unlink()
        with patch.object(os, 'replace', side_effect=OSError('replace failed')):
            self.publish()
        self.assertFalse(self.target.exists())
        self.assert_clean()


class IntegrationStructureTests(unittest.TestCase):
    def test_single_call_and_qualifying_guard(self):
        calls = [n for n in ast.walk(TREE) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == 'wr_hardsignal_json']
        self.assertEqual(len(calls), 1)
        guard = next(n for n in ast.walk(RUN) if isinstance(n, ast.If)
                     and ast.unparse(n.test) == 'self.data_ready and self.theta_0_list')
        position = next(i for i, n in enumerate(guard.body) if calls[0] in list(ast.walk(n)))
        self.assertEqual(guard.body[position - 1].value.func.attr, 'wr_xml')
        # Execute the real guard and call, without the hardware-dependent body.
        isolated = copy.deepcopy(guard)
        isolated.body = [copy.deepcopy(guard.body[position])]
        isolated.orelse = []
        code = compile(ast.Module(body=[isolated], type_ignores=[]), '<output guard>', 'exec')
        for ready, results, expected in [(True, [81], 1), (False, [81], 0), (True, [], 0)]:
            processor = SimpleNamespace(data_ready=ready, theta_0_list=results, wr_hardsignal_json=Mock())
            exec(code, {'self': processor})
            self.assertEqual(processor.wr_hardsignal_json.call_count, expected)

    def test_no_historical_debug_markers(self):
        for marker in ('STAGE_A', 'STAGE_B', 'STAGE_C', 'DOA_GATE', 'TRACE_', 'HS_TRACE_'):
            self.assertNotIn(marker, SOURCE)

    def test_ordinary_kraken_ast_unchanged_from_base(self):
        baseline = ast.parse(subprocess.check_output(['git', 'show', BASE_COMMIT + ':' + RELATIVE], cwd=ROOT))
        candidate = copy.deepcopy(TREE)
        candidate.body = [n for n in candidate.body if not (
            isinstance(n, ast.Import) and [alias.name for alias in n.names] == ['tempfile'])]
        cls = next(n for n in candidate.body if isinstance(n, ast.ClassDef) and n.name == 'SignalProcessor')
        cls.body = [n for n in cls.body if not (isinstance(n, ast.FunctionDef) and n.name == 'wr_hardsignal_json')]
        class RemoveExportCall(ast.NodeTransformer):
            def visit_Expr(self, node):
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
                    if node.value.func.attr == 'wr_hardsignal_json':
                        return None
                return self.generic_visit(node)
        candidate = RemoveExportCall().visit(candidate)
        self.assertEqual(ast.dump(candidate), ast.dump(baseline))


if __name__ == '__main__':
    unittest.main()
