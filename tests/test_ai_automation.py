"""Tests for the free, development-only AI verification entry point."""
import importlib.util
import hashlib
import contextlib
import io
import json
import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PATH = Path(__file__).resolve().parents[1] / 'tools/verify_ai.py'
spec = importlib.util.spec_from_file_location('verify_ai', PATH)
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class AiAutomationTests(unittest.TestCase):
    def test_default_runs_only_free_checks_and_propagates_failure(self):
        with contextlib.redirect_stdout(io.StringIO()), mock.patch.object(verify, 'run_tests', return_value=False) as tests, \
             mock.patch.object(verify, 'check_evidence', return_value=True) as evidence, \
             mock.patch.object(verify, 'check_artifact', side_effect=AssertionError('no artifact by default')):
            self.assertEqual(verify.main([]), 1)
            tests.assert_called_once()
            evidence.assert_called_once()

    def test_evidence_must_exist_match_hash_and_accounting(self):
        with contextlib.redirect_stderr(io.StringIO()), tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'evidence'
            shutil.copytree(verify.EVIDENCE, root)
            self.assertTrue(verify.check_evidence(root))
            path = root / 'report.json'
            original = path.read_text()
            data = json.loads(original)
            data['agreement']['matched'] = 1
            path.write_text(json.dumps(data))
            self.assertFalse(verify.check_evidence(root))
            changed_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            with mock.patch.object(verify, 'EVIDENCE_SHA256', (*verify.EVIDENCE_SHA256[:2], changed_hash)):
                self.assertFalse(verify.check_evidence(root))
            path.write_text(original)
            (root / 'simulation.json').write_text('{}')
            self.assertFalse(verify.check_evidence(root))
            (root / 'simulation.json').unlink()
            self.assertFalse(verify.check_evidence(root))

    def test_artifact_missing_fails(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertFalse(verify.check_artifact(Path('/definitely-missing-ai-test.whl')))

    def test_runner_process_propagates_missing_artifact_failure(self):
        import subprocess
        import sys
        result = subprocess.run([sys.executable, str(PATH), '--artifact', '/definitely-missing-ai-test.whl'],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1)
        self.assertIn('failed', result.stdout)

    def test_test_runner_does_not_pass_ambient_credentials(self):
        with mock.patch.dict('os.environ', {'OPENAI_API_KEY': 'ambient-secret'}), \
             mock.patch.object(verify, '_bounded', return_value=(0, b'')) as run:
            self.assertTrue(verify.run_tests())
            self.assertNotIn('OPENAI_API_KEY', run.call_args.args[2])

    @unittest.skipUnless(os.name == 'posix' and Path('/proc').is_dir(), 'requires POSIX and /proc')
    def test_test_runner_timeout_kills_descendant_and_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            pidfile = Path(directory) / 'child.pid'
            script = ("import subprocess,sys,time; "
                      "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)']); "
                      f"open({str(pidfile)!r},'w').write(str(child.pid)); time.sleep(20)")
            with mock.patch.object(verify, '_test_command', return_value=[sys.executable, '-c', script]), \
                 mock.patch.object(verify, 'TEST_TIMEOUT', 0.5), contextlib.redirect_stderr(io.StringIO()):
                self.assertFalse(verify.run_tests())
            status = Path('/proc') / pidfile.read_text() / 'status'
            try:
                child_status = status.read_text()
            except (FileNotFoundError, ProcessLookupError):
                return
            self.assertIn('State:\tZ', child_status)

    @unittest.skipUnless(os.name == 'posix', 'process groups require POSIX')
    def test_test_runner_propagates_failing_exit_and_diagnostics(self):
        command = [sys.executable, '-c', "print('fake test failed'); raise SystemExit(3)"]
        output = io.StringIO()
        with mock.patch.object(verify, '_test_command', return_value=command), contextlib.redirect_stdout(output):
            self.assertFalse(verify.run_tests())
        self.assertIn('fake test failed', output.getvalue())
