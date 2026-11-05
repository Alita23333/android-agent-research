"""Meaningful transfer-integrity tests; fixtures stay in isolated temp dirs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('exchange', Path(__file__).with_name('file-exchange.py'))
exchange = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exchange)

class ExchangeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='android-agent-exchange-test-')
        self.root = Path(self.temp.name)
        self.source = self.root/'source'; self.source.mkdir()
        (self.source/'HANDOFF.md').write_text('Synthetic handoff fixture', encoding='utf-8')
        self.metadata = {'protocolVersion': 1, 'packageId': 'codex-test-001',
                         'sender': 'codex', 'recipient': 'zcode', 'scope': 'transport test',
                         'baseline': 'test-only', 'changeSummary': 'synthetic fixture',
                         'completion': 'COMPLETE', 'missingItems': [],
                         'requiredPaths': ['HANDOFF.md'], 'fileRoles': {'HANDOFF.md': 'documentation'}}
        self.exchange = self.root/'exchange'

    def tearDown(self):
        self.temp.cleanup()

    def publish(self):
        meta = self.root/'spec.json'; meta.write_text(json.dumps(self.metadata), encoding='utf-8')
        return exchange.publish(self.exchange, self.source, meta)

    def test_roundtrip_complete_inventory(self):
        result = exchange.verify(self.publish())
        self.assertEqual(result['fileCount'], 1)
        self.assertEqual(result['contentReview'], 'NOT_PERFORMED')

    def test_missing_required_rejected(self):
        self.metadata['requiredPaths'].append('source/worker.kt')
        with self.assertRaises(ValueError): self.publish()

    def test_declared_partial_is_reported(self):
        self.metadata.update(completion='PARTIAL', missingItems=['worker source missing'])
        self.metadata['requiredPaths'].append('source/worker.kt')
        self.assertEqual(exchange.verify(self.publish())['missingPaths'], ['source/worker.kt'])

    def test_cannot_overwrite_sealed_package(self):
        self.publish()
        with self.assertRaises(ValueError): self.publish()

    def test_corrupt_transfer_rejected(self):
        p = self.publish(); (p/'bundle.zip').write_bytes(b'truncated')
        with self.assertRaises(ValueError): exchange.verify(p)

    def test_extra_delivery_file_rejected(self):
        p = self.publish(); (p/'hidden.txt').write_text('unexpected')
        with self.assertRaises(ValueError): exchange.verify(p)

    def test_secret_field_rejected(self):
        (self.source/'settings.json').write_text('{"apiKey":"fixture-secret"}')
        self.metadata['fileRoles']['settings.json'] = 'contract'
        with self.assertRaises(ValueError): self.publish()

    def test_placeholder_accepted(self):
        (self.source/'template.json').write_text('{"apiKey":"[REDACTED_SECRET]"}')
        self.metadata['fileRoles']['template.json'] = 'contract'
        self.assertEqual(exchange.verify(self.publish())['fileCount'], 2)

    def test_executor_state_rejected(self):
        (self.source/'.mimosa').mkdir(); (self.source/'.mimosa/state.json').write_text('{}')
        self.metadata['fileRoles']['.mimosa/state.json'] = 'result'
        with self.assertRaises(ValueError): self.publish()

    def test_unsafe_paths_rejected(self):
        for value in ['../escape', '/absolute', 'a/../b', 'a\\b', 'C:/data', 'CON.txt', 'trailing.', 'a//b']:
            with self.subTest(value=value):
                with self.assertRaises(ValueError): exchange.safe_path(value)

    def test_receipt_identity_bound(self):
        p = self.publish()
        with self.assertRaises(ValueError): exchange.receipt(self.exchange, p, 'codex', 'RECEIVED', 'fixture')
        q = exchange.receipt(self.exchange, p, 'zcode', 'RECEIVED', 'fixture')
        self.assertEqual(json.loads(q.read_text())['contentReview'], 'NOT_PERFORMED')

    def test_discovery_no_filename_needed_and_idempotent(self):
        self.publish()
        a = exchange.discover(self.exchange, 'zcode')
        self.assertEqual(a['pendingReview'], 1)
        self.assertTrue(a['deliveries'][0]['newlyReceived'])
        b = exchange.discover(self.exchange, 'zcode')
        self.assertFalse(b['deliveries'][0]['newlyReceived'])
        self.assertEqual(len(list((self.exchange/'receipts/zcode').glob('*.json'))), 1)

    def test_discovery_ignores_staging(self):
        lane = self.exchange/'codex-to-zcode'; lane.mkdir(parents=True)
        p = lane/'_staging-fixture'; p.mkdir(); (p/'READY.json').write_text('{}')
        self.assertEqual(exchange.discover(self.exchange, 'zcode')['deliveries'], [])

    def test_discovery_rejects_corrupt_and_does_not_ack(self):
        p = self.publish(); (p/'bundle.zip').write_bytes(b'truncated')
        result = exchange.discover(self.exchange, 'zcode')
        self.assertEqual(result['rejectedCount'], 1)
        self.assertFalse((self.exchange/'receipts/zcode').exists())

    def test_review_disposition_discovery(self):
        p = self.publish()
        exchange.receipt(self.exchange, p, 'zcode', 'NEEDS_REVISION', 'fixture missing evidence')
        self.assertEqual(exchange.discover(self.exchange, 'zcode')['pendingReview'], 0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
