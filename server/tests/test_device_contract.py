import base64
import json
import struct
import unittest
import uuid

from fastapi.testclient import TestClient

from relay.app import create_app
from relay.quota import QuotaDenied, QuotaUnavailable
from tests.test_turn import Backend, settings, wav


class DeviceContractTests(unittest.TestCase):
    def setUp(self):
        self.config = settings()
        self.headers = {'X-Device-Secret': self.config.device_secret, 'Content-Type': 'audio/wav'}

    def unpack(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'application/vnd.m5stack.turn+wav')
        magic, json_size, audio_size = struct.unpack('<4sII', response.content[:12])
        self.assertEqual(magic, b'M5R3')
        self.assertLessEqual(json_size, 16384)
        self.assertEqual(len(response.content), 12 + json_size + audio_size)
        metadata = json.loads(response.content[12:12 + json_size])
        self.assertEqual(metadata['version'], 3)
        self.assertNotIn('audio', metadata)
        return metadata, response.content[12 + json_size:]

    def test_binary_v3_preserves_hebrew_and_wav_without_base64_amplification(self):
        client = TestClient(create_app(self.config, Backend()))
        metadata, audio = self.unpack(client.post('/v3/turn', content=wav(), headers=self.headers))
        self.assertEqual(metadata['transcript'], 'שלום, מה השעה?')
        self.assertEqual(metadata['answer'], 'שלום! אני שומע אותך.')
        self.assertEqual(audio, wav())
        self.assertLess(len(audio), len(base64.b64encode(audio)))

    def test_notice_uses_fixed_text_and_never_calls_transcription_or_llm(self):
        spoken = []
        class NoticeOnly(Backend):
            async def transcribe(self, audio):
                raise AssertionError('notice must not transcribe')
            async def reply(self, text, private):
                raise AssertionError('notice must not invoke model')
            async def synthesize(self, text):
                spoken.append(text)
                return wav()
        client = TestClient(create_app(self.config, NoticeOnly()))
        self.assertEqual(client.post('/v3/notice').status_code, 401)
        metadata, audio = self.unpack(client.post('/v3/notice', headers=self.headers))
        self.assertEqual(metadata['answer'], 'העדכון הושלם. אני מוכן לשיחה ולחיפוש באינטרנט.')
        self.assertEqual(spoken, [metadata['answer']])
        self.assertEqual(audio, wav())

    def test_required_durable_admission_cannot_be_omitted_or_bypassed(self):
        config = settings(durable_quotas_required=True)
        client = TestClient(create_app(config, Backend()))
        self.assertEqual(client.post('/v3/turn', content=wav(), headers=self.headers).status_code, 503)
        self.assertEqual(client.post('/v3/notice', headers=self.headers).status_code, 503)

    def test_durable_denial_or_failure_never_starts_providers(self):
        class Never(Backend):
            async def transcribe(self, audio):
                raise AssertionError('quota bypass')
            async def synthesize(self, text):
                raise AssertionError('notice quota bypass')
        class Denied:
            async def admit(self, identifier):
                raise failure
        for failure, status in ((QuotaDenied('day'), 429), (QuotaDenied('duplicate'), 409),
                                (QuotaUnavailable(), 503)):
            with self.subTest(status=status):
                client = TestClient(create_app(self.config, Never(), quota=Denied()))
                for path in ('/v1/turn', '/v2/turn', '/v3/turn', '/v3/notice'):
                    self.assertEqual(client.post(path, content=wav(), headers=self.headers).status_code, status)

    def test_all_api_versions_share_durable_request_id_and_notice_deduplication(self):
        admitted = []
        class Quota:
            async def admit(self, identifier):
                admitted.append(identifier)
        client = TestClient(create_app(self.config, Backend(), quota=Quota()))
        identifier = str(uuid.uuid4())
        headers = self.headers | {'X-Request-ID': identifier}
        self.assertEqual(client.post('/v3/turn', content=wav(), headers=headers).status_code, 200)
        self.assertEqual(client.post('/v3/notice', headers=headers).status_code, 409)
        self.assertEqual(admitted, [identifier])
