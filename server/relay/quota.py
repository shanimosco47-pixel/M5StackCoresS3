"""Fail-closed durable admission; the document contains counters and opaque IDs only."""
import asyncio
import json
import math
import re
import time
import uuid
from datetime import datetime, timezone

import httpx


class QuotaDenied(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


class QuotaUnavailable(Exception):
    def __init__(self):
        super().__init__('quota_unavailable')


def _number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _counter(value):
    return type(value) is int and value >= 0


def _identifier(value):
    if not isinstance(value, str) or len(value) > 36:
        raise ValueError('invalid_request_id')
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise ValueError('invalid_request_id') from None


class FirestoreQuota:
    """Reserve one turn using Firestore's update-time/create preconditions.

    The optional client is a transport boundary for tests. The owned production
    client verifies TLS, ignores proxy/CA environment overrides and never follows
    redirects. No local admission cache or refunds can bypass durable counters.
    """

    def __init__(self, project, client=None, clock=time.time):
        if not isinstance(project, str) or not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', project):
            raise ValueError('invalid_project')
        self._project = project
        self._url = (f'https://firestore.googleapis.com/v1/projects/{project}'
                     '/databases/(default)/documents/voice_relay_limits/device')
        self._client = client
        self._clock = clock
        self._token = ''
        self._token_start = self._token_until = 0

    async def admit(self, identifier):
        identifier = _identifier(identifier)
        try:
            # A total deadline also bounds a server that continually drips bytes.
            async with asyncio.timeout(35):
                if self._client is not None:
                    await self._admit(self._client, identifier)
                else:
                    async with httpx.AsyncClient(verify=True, trust_env=False, follow_redirects=False) as client:
                        await self._admit(client, identifier)
        except (httpx.HTTPError, ValueError, TypeError, KeyError, OverflowError,
                OSError, TimeoutError, RecursionError):
            # Never expose provider bodies, token values, URLs or parser errors.
            raise QuotaUnavailable() from None

    async def _request(self, client, method, url, limit=65536, timeout=5, **kwargs):
        async with client.stream(method, url, timeout=timeout, follow_redirects=False, **kwargs) as response:
            payload = bytearray()
            async for chunk in response.aiter_bytes():
                if len(payload) + len(chunk) > limit:
                    raise ValueError('response_size')
                payload.extend(chunk)
            return response.status_code, response.headers, bytes(payload)

    async def _access_token(self, client, now):
        if self._token and self._token_start <= now < self._token_until:
            return self._token
        status, headers, payload = await self._request(
            client, 'GET',
            'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token',
            limit=16384, timeout=3, headers={'Metadata-Flavor': 'Google'})
        if status != 200 or headers.get('Metadata-Flavor') != 'Google':
            raise ValueError('metadata_status')
        data = json.loads(payload)
        token, expires = data['access_token'], data['expires_in']
        if (not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9._~+/=-]{1,8192}', token)
                or not _number(expires) or not 0 < expires <= 3600
                or data.get('token_type') != 'Bearer'):
            raise ValueError('metadata_token')
        self._token = token
        self._token_start = now
        self._token_until = now + min(300, max(0, expires - 30))
        return token

    def _state(self, payload):
        document = json.loads(payload)
        if set(document['fields']) != {'state'} or set(document['fields']['state']) != {'stringValue'}:
            raise ValueError('document_shape')
        encoded = document['fields']['state']['stringValue']
        if not isinstance(encoded, str):
            raise ValueError('state_encoding')
        state = json.loads(encoded)
        if (not isinstance(state, dict)
                or set(state) != {'v', 'minute', 'day', 'day_count', 'month', 'month_chars', 'recent'}
                or type(state['v']) is not int or state['v'] != 1
                or not all(_counter(state[key]) for key in ('day', 'day_count', 'month', 'month_chars'))
                or not isinstance(state['minute'], list) or len(state['minute']) > 6
                or not all(_number(stamp) for stamp in state['minute'])
                or not isinstance(state['recent'], dict) or len(state['recent']) > 256):
            raise ValueError('state_shape')
        if any(_identifier(key) != key or not _number(stamp) for key, stamp in state['recent'].items()):
            raise ValueError('state_replay')
        update = document['updateTime']
        if not isinstance(update, str) or not 1 <= len(update) <= 128:
            raise ValueError('document_version')
        return state, update

    async def _admit(self, client, identifier):
        for _ in range(3):
            now = self._clock()
            if not _number(now):
                raise ValueError('clock')
            utc = datetime.fromtimestamp(now, tz=timezone.utc)
            day, month = int(now // 86400), utc.year * 12 + utc.month
            token = await self._access_token(client, now)
            headers = {'Authorization': f'Bearer {token}', 'x-goog-user-project': self._project}
            status, _, payload = await self._request(client, 'GET', self._url, headers=headers)
            if status == 404:
                state = {'v': 1, 'minute': [], 'day': day, 'day_count': 0,
                         'month': month, 'month_chars': 0, 'recent': {}}
                precondition = {'currentDocument.exists': 'false'}
            elif status == 200:
                state, update = self._state(payload)
                precondition = {'currentDocument.updateTime': update}
            else:
                raise ValueError('read_status')
            # Do not reset a future bucket if this process's clock moves backwards.
            if state['day'] > day or state['month'] > month:
                raise ValueError('clock_regression')
            if state['day'] < day:
                state['day'], state['day_count'] = day, 0
            if state['month'] < month:
                state['month'], state['month_chars'] = month, 0
            state['minute'] = [stamp for stamp in state['minute'] if stamp > now - 60]
            state['recent'] = {key: stamp for key, stamp in state['recent'].items() if stamp > now - 600}
            if identifier in state['recent']:
                raise QuotaDenied('duplicate')
            if len(state['minute']) >= 6:
                raise QuotaDenied('minute')
            if state['day_count'] >= 100:
                raise QuotaDenied('day')
            if state['month_chars'] + 1000 > 3000000:
                raise QuotaDenied('month')
            if len(state['recent']) >= 256:
                raise QuotaDenied('capacity')
            state['minute'].append(now)
            state['recent'][identifier] = now
            state['day_count'] += 1
            state['month_chars'] += 1000
            encoded = json.dumps(state, separators=(',', ':'), allow_nan=False)
            body = {'fields': {'state': {'stringValue': encoded}}}
            status, _, payload = await self._request(
                client, 'PATCH', self._url, headers=headers, json=body,
                params={'updateMask.fieldPaths': 'state', **precondition})
            if status in (409, 412):
                continue  # Re-read authority and re-evaluate all limits before retrying.
            if status != 200:
                raise ValueError('write_status')
            committed = json.loads(payload)
            if (not isinstance(committed, dict)
                    or not isinstance(committed.get('updateTime'), str) or not committed['updateTime']):
                raise ValueError('commit_response')
            return
        raise QuotaUnavailable()
