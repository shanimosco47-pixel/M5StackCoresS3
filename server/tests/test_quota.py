import asyncio
import copy
import importlib.util
import json
import unittest
import uuid
from datetime import datetime, timezone

import httpx


def identifier(number):
    return str(uuid.UUID(int=number))


class Firestore:
    """Persistent HTTP boundary, including real precondition enforcement."""

    def __init__(self, test):
        self.test = test
        self.state = None
        self.version = 0
        self.reads = self.writes = self.tokens = self.conflicts = 0
        self.requests = []
        self.mode = ''
        self.barrier = None

    async def __call__(self, request):
        self.requests.append(request)
        self.test.assertFalse(request.extensions['timeout']['read'] is None)
        if request.url.host == 'metadata.google.internal':
            self.test.assertEqual(str(request.url), 'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token')
            self.test.assertEqual(request.headers.get('metadata-flavor'), 'Google')
            self.test.assertNotIn('authorization', request.headers)
            self.test.assertEqual(request.extensions['timeout']['read'], 3)
            self.tokens += 1
            if self.mode == 'metadata_error':
                return httpx.Response(503, text='private provider failure')
            if self.mode == 'metadata_redirect':
                return httpx.Response(302, headers={'Location': 'https://attacker.invalid/'})
            if self.mode == 'metadata_large':
                return httpx.Response(200, content=b'x' * 16385)
            return httpx.Response(200, headers={'Metadata-Flavor': 'Google'}, json={
                'access_token': 'synthetic-attached-token', 'expires_in': 3600, 'token_type': 'Bearer'})
        self.test.assertEqual(str(request.url.copy_with(query=None)), 'https://firestore.googleapis.com/v1/projects/test-project/databases/(default)/documents/voice_relay_limits/device')
        self.test.assertEqual(request.headers['authorization'], 'Bearer synthetic-attached-token')
        self.test.assertEqual(request.headers['x-goog-user-project'], 'test-project')
        if self.mode == 'backend_error':
            return httpx.Response(403, text='sensitive backend diagnostic')
        if self.mode == 'backend_redirect':
            return httpx.Response(307, headers={'Location': 'https://attacker.invalid/'})
        if self.mode == 'backend_large':
            return httpx.Response(200, content=b'x' * 65537)
        if self.mode == 'transport_error':
            raise httpx.ReadTimeout('sensitive transport diagnostic')
        if request.method == 'GET':
            self.reads += 1
            response = httpx.Response(404) if self.state is None else httpx.Response(200, json={
                'fields': {'state': {'stringValue': json.dumps(self.state)}},
                'updateTime': f'2026-11-21T00:00:00.{self.version:09d}Z'})
            if self.barrier is not None:
                barrier = self.barrier
                self.barrier = None
                await barrier.wait()
            return response
        self.test.assertEqual(request.method, 'PATCH')
        self.writes += 1
        body = json.loads(request.content)
        self.test.assertEqual(set(body), {'fields'})
        self.test.assertEqual(set(body['fields']), {'state'})
        self.test.assertEqual(set(body['fields']['state']), {'stringValue'})
        self.test.assertLessEqual(len(request.content), 65536)
        params = dict(request.url.params)
        self.test.assertEqual(params.pop('updateMask.fieldPaths'), 'state')
        correct = ({'currentDocument.exists': 'false'} if self.state is None else {
            'currentDocument.updateTime': f'2026-11-21T00:00:00.{self.version:09d}Z'})
        if params != correct or self.mode == 'always_conflict':
            self.conflicts += 1
            return httpx.Response(412)
        self.state = json.loads(body['fields']['state']['stringValue'])
        self.version += 1
        return httpx.Response(200, json={'updateTime': f'2026-11-21T00:00:00.{self.version:09d}Z'})


class QuotaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.assertIsNotNone(importlib.util.find_spec('relay.quota'), 'durable quota implementation missing')
        from relay.quota import FirestoreQuota, QuotaDenied, QuotaUnavailable
        self.quota_type = FirestoreQuota
        self.denied = QuotaDenied
        self.unavailable = QuotaUnavailable
        self.now = datetime(2026, 11, 21, tzinfo=timezone.utc).timestamp()
        self.db = Firestore(self)
        # Intentionally enable redirects on the injected client: quota must override it.
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(self.db), follow_redirects=True)
        self.addAsyncCleanup(self.client.aclose)
        self.first = self.quota()

    def quota(self):
        return self.quota_type('test-project', client=self.client, clock=lambda: self.now)

    async def assert_denied(self, quota, number, reason):
        version = self.db.version
        with self.assertRaises(self.denied) as raised:
            await quota.admit(identifier(number))
        self.assertEqual(raised.exception.reason, reason)
        self.assertEqual(self.db.version, version, 'denials must never commit')

    async def test_two_instances_share_minute_budget_and_replay_protection(self):
        second = self.quota()
        await self.first.admit(identifier(1))
        await self.assert_denied(second, 1, 'duplicate')
        for number in range(2, 7):
            await second.admit(identifier(number))
        await self.assert_denied(self.first, 7, 'minute')
        self.assertEqual(self.db.version, 6)
        self.assertEqual(self.db.state['day_count'], 6)
        self.assertEqual(self.db.state['month_chars'], 6000)

    async def test_rolling_minute_and_exact_ten_minute_replay_expiry(self):
        for number in range(1, 7):
            await self.first.admit(identifier(number))
        self.now += 59.999
        await self.assert_denied(self.first, 7, 'minute')
        self.now += .001
        await self.first.admit(identifier(7))
        self.now += 539.999
        await self.assert_denied(self.quota(), 1, 'duplicate')
        self.now += .001
        await self.quota().admit(identifier(1))

    async def test_daily_budget_resets_at_utc_midnight(self):
        for number in range(1, 101):
            await self.quota().admit(identifier(number))
            self.now += 61
        await self.assert_denied(self.first, 101, 'day')
        self.now = datetime(2026, 11, 22, tzinfo=timezone.utc).timestamp()
        await self.first.admit(identifier(101))
        self.assertEqual(self.db.state['day_count'], 1)
        self.assertEqual(self.db.state['month_chars'], 101000)

    async def test_month_budget_is_reserved_before_work_and_resets_in_utc(self):
        await self.first.admit(identifier(1))
        self.db.state['month_chars'] = 2999000
        self.now += 61
        await self.first.admit(identifier(2))
        self.now += 61
        await self.assert_denied(self.quota(), 3, 'month')
        self.now = datetime(2026, 12, 1, tzinfo=timezone.utc).timestamp()
        await self.quota().admit(identifier(3))
        self.assertEqual(self.db.state['month_chars'], 1000)
        self.assertEqual(self.db.state['day_count'], 1)

    async def test_racing_instances_cannot_bypass_last_minute_slot(self):
        for number in range(1, 6):
            await self.first.admit(identifier(number))
        gate = asyncio.Event()
        self.db.barrier = gate
        delayed = asyncio.create_task(self.first.admit(identifier(6)))
        await asyncio.sleep(0)
        await self.quota().admit(identifier(7))
        gate.set()
        with self.assertRaises(self.denied) as raised:
            await delayed
        self.assertEqual(raised.exception.reason, 'minute')
        self.assertEqual(self.db.conflicts, 1)
        self.assertEqual(self.db.version, 6)
        self.assertEqual(self.db.state['month_chars'], 6000)

    async def test_racing_creation_of_same_uuid_admits_only_one(self):
        gate = asyncio.Event()
        self.db.barrier = gate
        delayed = asyncio.create_task(self.first.admit(identifier(1)))
        await asyncio.sleep(0)
        await self.quota().admit(identifier(1))
        gate.set()
        with self.assertRaises(self.denied) as raised:
            await delayed
        self.assertEqual(raised.exception.reason, 'duplicate')
        self.assertEqual(self.db.conflicts, 1)
        self.assertEqual(self.db.version, 1)
        self.assertEqual(self.db.state['month_chars'], 1000)

    async def test_malformed_commit_response_fails_closed_without_refund(self):
        async def malformed(request):
            response = await self.db(request)
            if request.method == 'PATCH' and response.status_code == 200:
                return httpx.Response(200, json=[])
            return response
        async with httpx.AsyncClient(transport=httpx.MockTransport(malformed)) as client:
            quota = self.quota_type('test-project', client=client, clock=lambda: self.now)
            with self.assertRaises(self.unavailable):
                await quota.admit(identifier(1))
        self.assertEqual(self.db.state['month_chars'], 1000)
        await self.assert_denied(self.quota(), 1, 'duplicate')

    async def test_backwards_day_or_month_clock_fails_closed(self):
        await self.first.admit(identifier(1))
        self.now -= 86400
        with self.assertRaises(self.unavailable):
            await self.quota().admit(identifier(2))
        self.assertEqual(self.db.version, 1)

    async def test_cas_409_rereads_and_commits_once(self):
        failed = False

        async def conflict_once(request):
            nonlocal failed
            response = await self.db(request)
            if request.method == 'GET' and request.url.host == 'firestore.googleapis.com' and not failed:
                # Simulate an unrelated concurrent successful admission after GET.
                await self.quota().admit(identifier(99))
            if request.method == 'PATCH' and response.status_code == 412:
                failed = True
                return httpx.Response(409)
            return response

        async with httpx.AsyncClient(transport=httpx.MockTransport(conflict_once)) as client:
            quota = self.quota_type('test-project', client=client, clock=lambda: self.now)
            await quota.admit(identifier(1))
        self.assertEqual(self.db.version, 2)
        self.assertEqual(self.db.state['month_chars'], 2000)
        self.assertEqual(self.db.conflicts, 1)

    async def test_conflicts_retried_at_most_three_times_fail_closed(self):
        self.db.mode = 'always_conflict'
        with self.assertRaises(self.unavailable):
            await self.first.admit(identifier(1))
        self.assertEqual(self.db.writes, 3)
        self.assertEqual(self.db.reads, 3)
        self.assertIsNone(self.db.state)

    async def test_full_replay_table_rejects_without_eviction(self):
        await self.first.admit(identifier(1))
        self.db.state['recent'] = {identifier(n): self.now for n in range(1, 257)}
        original = copy.deepcopy(self.db.state)
        await self.assert_denied(self.quota(), 257, 'capacity')
        self.assertEqual(self.db.state, original)
        self.now += 600
        await self.quota().admit(identifier(257))
        self.assertEqual(len(self.db.state['recent']), 1)

    async def test_metadata_and_backend_failures_never_admit_or_leak_details(self):
        for mode in ('metadata_error', 'metadata_redirect', 'metadata_large',
                     'backend_error', 'backend_redirect', 'backend_large', 'transport_error'):
            with self.subTest(mode=mode):
                self.db.mode = mode
                with self.assertRaises(self.unavailable) as raised:
                    await self.quota().admit(identifier(1))
                self.assertEqual(str(raised.exception), 'quota_unavailable')
                self.assertIsNone(raised.exception.__cause__)
                self.assertIsNone(self.db.state)
        self.assertFalse(any(r.url.host == 'attacker.invalid' for r in self.db.requests))

    async def test_corrupt_state_fails_closed(self):
        await self.first.admit(identifier(1))
        valid = copy.deepcopy(self.db.state)
        for key, value in (('day_count', -1), ('month_chars', True), ('recent', {'not-uuid': self.now}),
                           ('minute', [float('nan')]), ('v', 99)):
            with self.subTest(key=key):
                self.db.state = dict(valid, **{key: value})
                with self.assertRaises(self.unavailable):
                    await self.quota().admit(identifier(2))
                self.assertEqual(self.db.version, 1)

    async def test_metadata_token_cache_is_short_lived(self):
        await self.first.admit(identifier(1))
        await self.first.admit(identifier(2))
        self.assertEqual(self.db.tokens, 1)
        self.now += 301
        await self.first.admit(identifier(3))
        self.assertEqual(self.db.tokens, 2)

    async def test_invalid_project_and_request_ids_never_reach_network(self):
        for project in ('', '../wrong', 'https://attacker.invalid', 'test-project?key=bad'):
            with self.assertRaises(ValueError):
                self.quota_type(project, client=self.client)
        for value in ('', 'text', '1' * 1000):
            with self.assertRaises(ValueError):
                await self.first.admit(value)
        self.assertFalse(self.db.requests)
