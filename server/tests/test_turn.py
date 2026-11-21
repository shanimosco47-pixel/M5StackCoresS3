import asyncio
import base64
import io
import unittest
import uuid
import wave

import httpx
from fastapi.testclient import TestClient

from relay.app import create_app
from relay.config import Settings
from relay.service import Answer, UpstreamError


def wav(seconds=0.6, sample=1000, rate=16000):
    output = io.BytesIO()
    with wave.open(output, 'wb') as stream:
        stream.setparams((1, 2, rate, 0, 'NONE', 'not compressed'))
        stream.writeframes(int(sample).to_bytes(2, 'little', signed=True) * int(rate * seconds))
    return output.getvalue()


def settings(**changes):
    values = dict(device_secret='d' * 32, groq_key='test-groq', openrouter_key='test-router',
                  azure_key='test-azure', azure_region='westeurope', model='example/model',
                  allowed_models=('example/model',), private_approved=True)
    return Settings(**(values | changes))


class Backend:
    async def transcribe(self, audio):
        return 'שלום, מה השעה?'

    async def reply(self, text, private):
        return Answer('שלום! אני שומע אותך.', [])

    async def synthesize(self, text):
        return wav()


class TurnTests(unittest.TestCase):
    def setUp(self):
        self.config = settings()
        self.client = TestClient(create_app(self.config, Backend()))
        self.headers = {'X-Device-Secret': self.config.device_secret, 'Content-Type': 'audio/wav'}

    def turn(self, path='/v2/turn', audio=None, headers=None):
        return self.client.post(path, content=wav() if audio is None else audio,
                                headers=self.headers | (headers or {}))

    def test_unauthenticated_audio_is_rejected(self):
        response = self.client.post('/v2/turn', content=wav())
        self.assertEqual(response.status_code, 401)
        self.assertNotIn('test-groq', response.text)

    def test_hebrew_text_and_valid_audio_share_one_versioned_response(self):
        response = self.turn()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['version'], 2)
        self.assertEqual(body['transcript'], 'שלום, מה השעה?')
        self.assertEqual(body['answer'], 'שלום! אני שומע אותך.')
        self.assertEqual(body['audio']['mime_type'], 'audio/wav')
        self.assertEqual(base64.b64decode(body['audio']['base64']), wav())
        uuid.UUID(body['request_id'])
        self.assertEqual(response.headers['cache-control'], 'no-store')

    def test_v1_preserves_wav_contract(self):
        response = self.turn('/v1/turn')
        self.assertEqual(response.headers['content-type'], 'audio/wav')
        self.assertEqual(response.content, wav())

    def test_malformed_and_truncated_wav_are_rejected(self):
        for body in (b'not wav', wav()[:-10]):
            with self.subTest(body_size=len(body)):
                self.assertEqual(self.turn(audio=body).status_code, 422)

    def test_wrong_sample_rate_is_rejected(self):
        self.assertEqual(self.turn(audio=wav(rate=8000)).status_code, 422)

    def test_short_or_silent_recording_does_not_generate_a_reply(self):
        for audio in (wav(seconds=0.1), wav(sample=0)):
            self.assertEqual(self.turn(audio=audio).status_code, 204)

    def test_actual_body_limit_is_enforced_without_trusting_content_length(self):
        response = self.client.post('/v2/turn', content=iter([b'x' * 600000, b'x' * 600000]),
                                    headers=self.headers)
        self.assertEqual(response.status_code, 413)

    def test_wrong_media_type_is_rejected(self):
        self.assertEqual(self.turn(headers={'Content-Type': 'application/json'}).status_code, 415)

    def test_private_route_requires_explicit_provider_chain_approval(self):
        client = TestClient(create_app(settings(private_approved=False), Backend()))
        response = client.post('/v2/turn', content=wav(), headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error'], 'private_route_unavailable')

    def test_playground_is_explicit_and_does_not_enable_private_context(self):
        class Playground(Backend):
            async def reply(self, text, private):
                if private:
                    raise AssertionError('playground was routed as private')
                return Answer('ניסוי ציבורי', [])
        client = TestClient(create_app(settings(private_approved=False), Playground()))
        response = client.post('/v2/turn', content=wav(), headers=self.headers | {'X-Profile': 'playground'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['answer'], 'ניסוי ציבורי')

    def test_client_cannot_select_arbitrary_model_or_profile(self):
        self.assertEqual(self.turn(headers={'X-Profile': 'unknown'}).status_code, 400)
        client = TestClient(create_app(settings(allowed_models=('approved/model',)), Backend()))
        response = client.post('/v2/turn', content=wav(), headers=self.headers)
        self.assertEqual(response.status_code, 503)

    def test_bad_request_id_is_rejected(self):
        self.assertEqual(self.turn(headers={'X-Request-ID': '../bad'}).status_code, 400)

    def test_upstream_errors_expose_only_stage_and_request_id(self):
        class Broken(Backend):
            async def transcribe(self, audio):
                raise UpstreamError('stt', 'private provider body and key')
        client = TestClient(create_app(self.config, Broken()))
        response = client.post('/v2/turn', content=wav(), headers=self.headers)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.headers['x-error-stage'], 'stt')
        self.assertNotIn('private provider', response.text)

    def test_empty_transcript_is_no_content(self):
        class Empty(Backend):
            async def transcribe(self, audio):
                return '  '
        client = TestClient(create_app(self.config, Empty()))
        self.assertEqual(client.post('/v2/turn', content=wav(), headers=self.headers).status_code, 204)

    def test_bad_tts_audio_is_never_sent_to_device(self):
        class Broken(Backend):
            async def synthesize(self, text):
                return b'not a WAV file'
        client = TestClient(create_app(self.config, Broken()))
        response = client.post('/v2/turn', content=wav(), headers=self.headers)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.headers['x-error-stage'], 'tts')

    def test_local_rate_limit_stops_additional_provider_turns(self):
        client = TestClient(create_app(settings(requests_per_minute=1), Backend()))
        self.assertEqual(client.post('/v2/turn', content=wav(), headers=self.headers).status_code, 200)
        self.assertEqual(client.post('/v2/turn', content=wav(), headers=self.headers).status_code, 429)

    def test_unconfigured_process_is_live_but_not_ready(self):
        client = TestClient(create_app(Settings(), Backend()))
        self.assertEqual(client.get('/healthz').status_code, 200)
        self.assertEqual(client.get('/readyz').status_code, 503)
        self.assertEqual(client.post('/v2/turn', content=wav()).status_code, 503)

    def test_full_replay_cache_preserves_existing_ids_after_silent_uploads(self):
        identifier = str(uuid.uuid4())
        headers = self.headers | {'X-Request-ID': identifier}
        self.assertEqual(self.turn(headers=headers).status_code, 200)
        statuses = [self.turn(audio=wav(sample=0)).status_code for _ in range(300)]
        self.assertIn(429, statuses)  # New traffic must be refused before live replay IDs are lost.
        self.assertEqual(self.turn(headers=headers).status_code, 409)

    def test_logs_do_not_contain_transcript_or_answer(self):
        with self.assertLogs('relay', level='INFO') as logs:
            self.assertEqual(self.turn().status_code, 200)
        joined = '\n'.join(logs.output)
        self.assertNotIn('מה השעה', joined)
        self.assertNotIn('שומע אותך', joined)
        self.assertNotIn(self.config.device_secret, joined)


class CancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_reserves_request_id_before_other_requests_run(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def body():
            started.set()
            await release.wait()
            yield wav()
        config = settings()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(create_app(config, Backend())), base_url='http://test') as client:
            identifier = str(uuid.uuid4())
            headers = {'X-Device-Secret': config.device_secret, 'Content-Type': 'audio/wav', 'X-Request-ID': identifier}
            pending = asyncio.create_task(client.post('/v2/turn', content=body(), headers=headers))
            await asyncio.wait_for(started.wait(), 2)
            try:
                duplicate = await client.post('/v2/turn', content=wav(), headers=headers)
                self.assertIn(duplicate.status_code, (409, 429))
            finally:
                release.set()
                completed = await pending
            self.assertEqual(completed.status_code, 200)
            self.assertEqual((await client.post('/v2/turn', content=wav(), headers=headers)).status_code, 409)

    async def test_cancel_during_upload_prevents_provider_work_and_accepts_uppercase_id(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def body():
            started.set()
            await release.wait()
            yield wav()
        class NeverCallProviders(Backend):
            async def transcribe(self, audio):
                raise AssertionError('cancelled upload reached provider')
        config = settings()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(create_app(config, NeverCallProviders())), base_url='http://test') as client:
            identifier = str(uuid.uuid4()).upper()
            headers = {'X-Device-Secret': config.device_secret, 'Content-Type': 'audio/wav', 'X-Request-ID': identifier}
            pending = asyncio.create_task(client.post('/v2/turn', content=body(), headers=headers))
            await asyncio.wait_for(started.wait(), 2)
            cancelled = await client.delete('/v2/turn/' + identifier, headers=headers)
            release.set()
            self.assertEqual(cancelled.status_code, 204)
            self.assertEqual((await pending).status_code, 409)

    async def test_upload_deadline_releases_device_for_next_turn(self):
        async def stalled():
            await asyncio.Event().wait()
            yield wav()
        config = settings(turn_timeout=0.1)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(create_app(config, Backend())), base_url='http://test') as client:
            headers = {'X-Device-Secret': config.device_secret, 'Content-Type': 'audio/wav'}
            response = await asyncio.wait_for(client.post('/v2/turn', content=stalled(), headers=headers), 0.7)
            self.assertEqual(response.status_code, 504)
            self.assertEqual((await client.post('/v2/turn', content=wav(), headers=headers)).status_code, 200)

    async def test_cancel_turn_stops_work_and_releases_busy_device(self):
        started = asyncio.Event()
        cancelled = asyncio.Event()
        class Slow(Backend):
            async def transcribe(self, audio):
                started.set()
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    cancelled.set()
                    raise
        config = settings()
        app = create_app(config, Slow())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
            headers = {'X-Device-Secret': config.device_secret, 'Content-Type': 'audio/wav'}
            identifier = str(uuid.uuid4())
            pending = asyncio.create_task(client.post('/v2/turn', content=wav(), headers=headers | {'X-Request-ID': identifier}))
            await asyncio.wait_for(started.wait(), 2)
            busy = await client.post('/v2/turn', content=wav(), headers=headers)
            self.assertEqual(busy.status_code, 429)
            denied = await client.delete('/v2/turn/' + identifier)
            self.assertEqual(denied.status_code, 401)
            response = await client.delete('/v2/turn/' + identifier, headers=headers)
            self.assertEqual(response.status_code, 204)
            turn = await asyncio.wait_for(pending, 2)
            self.assertEqual(turn.status_code, 409)
            self.assertTrue(cancelled.is_set())


if __name__ == '__main__':
    unittest.main()
