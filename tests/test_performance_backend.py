"""Concurrency and lifetime contracts for read-path optimisations."""
import threading
import time
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest import mock

from skillsmgr import hygiene, store


class CoalescingContracts(unittest.TestCase):
    def setUp(self):
        self.flights = {}
        self.lock = threading.Lock()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.addCleanup(self.release.set)

    def read(self, key, fn):
        return store._coalesced_read(self.flights, self.lock, key, fn)

    def wait_for_waiters(self, count):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with self.lock:
                if self.flights.get('a', {}).get('waiters', 0) == count:
                    return
            time.sleep(.001)
        self.fail('waiters did not join flight')

    def test_concurrent_results_are_nested_independent_and_single_read(self):
        calls = []
        def produce():
            calls.append(1)
            self.entered.set()
            self.release.wait(3)
            return {'nested': {'value': 'original'}}
        with ThreadPoolExecutor(max_workers=3) as pool:
            owner = pool.submit(self.read, 'a', produce)
            self.assertTrue(self.entered.wait(3))
            waiters = [pool.submit(self.read, 'a', produce) for _ in range(2)]
            self.wait_for_waiters(2)
            self.release.set()
            values = [owner.result(3)] + [f.result(3) for f in waiters]
        self.assertEqual([1], calls)
        values[0]['nested']['value'] = 'changed'
        values[1]['nested']['value'] = 'other'
        self.assertEqual('original', values[2]['nested']['value'])
        self.assertEqual('other', values[1]['nested']['value'])

    def test_failed_read_wakes_waiters_and_retry_is_fresh(self):
        def fail():
            self.entered.set()
            self.release.wait(3)
            raise ValueError('read failed')
        with ThreadPoolExecutor(max_workers=3) as pool:
            owner = pool.submit(self.read, 'a', fail)
            self.assertTrue(self.entered.wait(3))
            waiters = [pool.submit(self.read, 'a', fail) for _ in range(2)]
            self.wait_for_waiters(2)
            self.release.set()
            for future in [owner, *waiters]:
                with self.assertRaisesRegex(ValueError, 'read failed'):
                    future.result(3)
        self.assertEqual({'fresh': True}, self.read('a', lambda: {'fresh': True}))

    def test_snapshot_failure_wakes_waiters_and_retry_is_fresh(self):
        class Uncopyable:
            def __deepcopy__(self, memo):
                raise ValueError('snapshot failed')
        def produce():
            self.entered.set()
            self.release.wait(3)
            return Uncopyable()
        with ThreadPoolExecutor(max_workers=3) as pool:
            owner = pool.submit(self.read, 'a', produce)
            self.assertTrue(self.entered.wait(3))
            waiters = [pool.submit(self.read, 'a', produce) for _ in range(2)]
            self.wait_for_waiters(2)
            self.release.set()
            for future in [owner, *waiters]:
                with self.assertRaisesRegex(ValueError, 'snapshot failed'):
                    future.result(3)
        self.assertEqual('fresh', self.read('a', lambda: 'fresh'))

    def test_snapshot_does_not_block_different_key(self):
        snapshot_entered = threading.Event()
        snapshot_release = threading.Event()
        self.addCleanup(snapshot_release.set)
        class SlowCopy:
            def __deepcopy__(self, memo):
                snapshot_entered.set()
                if not snapshot_release.wait(3):
                    raise TimeoutError('snapshot blocked')
                return 'copied'
        def produce():
            self.entered.set()
            self.release.wait(3)
            return SlowCopy()
        with ThreadPoolExecutor(max_workers=3) as pool:
            owner = pool.submit(self.read, 'a', produce)
            self.assertTrue(self.entered.wait(3))
            waiter = pool.submit(self.read, 'a', produce)
            self.wait_for_waiters(1)
            self.release.set()
            self.assertTrue(snapshot_entered.wait(3))
            other = pool.submit(self.read, 'b', lambda: 'independent')
            self.assertEqual('independent', other.result(1))
            snapshot_release.set()
            owner.result(3)
            self.assertEqual('copied', waiter.result(3))


class HygieneMemoContracts(unittest.TestCase):
    def test_each_report_resolves_identity_again(self):
        records = [{'name': 'alpha', 'scope': 'global', 'path': '/tmp/alpha'}]
        real = hygiene._resolve_identity
        with mock.patch.object(hygiene, '_resolve_identity', wraps=real) as resolve:
            hygiene.hygiene_report(records, scope='global')
            self.assertEqual(1, resolve.call_count)
            hygiene.hygiene_report(records, scope='global')
            self.assertEqual(2, resolve.call_count)

    def test_changed_symlink_is_resolved_fresh_on_next_report(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            first, second, link = root / 'first', root / 'second', root / 'link'
            first.mkdir()
            second.mkdir()
            try:
                link.symlink_to(first, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f'symlinks unavailable: {exc}')
            records = [{'name': 'alpha', 'scope': 'global', 'path': str(link)}]
            resolved = []
            real = hygiene._resolve_identity
            def observe(value):
                result = real(value)
                resolved.append(result)
                return result
            with mock.patch.object(hygiene, '_resolve_identity', side_effect=observe):
                hygiene.hygiene_report(records, scope='global')
                link.unlink()
                link.symlink_to(second, target_is_directory=True)
                hygiene.hygiene_report(records, scope='global')
            self.assertEqual([str(first.resolve()), str(second.resolve())], resolved)

    def test_nested_and_failing_reports_restore_outer_memo(self):
        record = {'name': 'alpha', 'scope': 'global', 'path': '/tmp/alpha'}
        outer_memo = None
        def nested(records, *, scope, max_instances):
            nonlocal outer_memo
            if scope == 'outer':
                outer_memo = hygiene._RESOLVED_IDENTITIES.get()
                hygiene._identity(record)
                with self.assertRaisesRegex(ValueError, 'inner failed'):
                    hygiene.hygiene_report([], scope='inner')
                self.assertIs(outer_memo, hygiene._RESOLVED_IDENTITIES.get())
                hygiene._identity(record)
                return {}
            raise ValueError('inner failed')
        with mock.patch.object(hygiene, '_hygiene_report', side_effect=nested), \
             mock.patch.object(hygiene, '_resolve_identity', wraps=hygiene._resolve_identity) as resolve:
            hygiene.hygiene_report([], scope='outer')
            self.assertEqual(1, resolve.call_count)
        self.assertIsNone(hygiene._RESOLVED_IDENTITIES.get())

    def test_concurrent_reports_do_not_share_memo(self):
        barrier = threading.Barrier(2)
        record = {'name': 'alpha', 'scope': 'global', 'path': '/tmp/alpha'}
        def report(records, *, scope, max_instances):
            hygiene._identity(record)
            barrier.wait(timeout=3)
            hygiene._identity(record)
            return {}
        with mock.patch.object(hygiene, '_hygiene_report', side_effect=report), \
             mock.patch.object(hygiene, '_resolve_identity', wraps=hygiene._resolve_identity) as resolve:
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(hygiene.hygiene_report, [], scope='global') for _ in range(2)]
                for future in futures:
                    future.result(3)
            self.assertEqual(2, resolve.call_count)
