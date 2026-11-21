import asyncio
import base64
import hmac
import json
import logging
import struct
import time
import uuid
from collections import deque

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect

from .audio import MAX_INPUT_BYTES, MAX_OUTPUT_BYTES, pcm_frames, too_quiet_or_short
from .config import Settings
from .quota import FirestoreQuota, QuotaDenied, QuotaUnavailable
from .service import Answer, UpstreamError, run_turn

log = logging.getLogger('relay')


NOTICE_TEXT = 'העדכון הושלם. אני מוכן לשיחה ולחיפוש באינטרנט.'


def create_app(settings: Settings, backend, quota=None) -> FastAPI:
    app = FastAPI(title='Hebrew CoreS3 relay', docs_url=None, redoc_url=None)
    active = {}
    recent = {}
    admissions = deque()

    def configured():
        return settings.ready and (not settings.durable_quotas_required or quota is not None)

    def error(status, name, identifier=None, stage=None):
        body = {'error': name}
        if identifier:
            body['request_id'] = identifier
        headers = {'Cache-Control': 'no-store'}
        if stage:
            headers['X-Error-Stage'] = stage
        return JSONResponse(body, status_code=status, headers=headers)

    def authenticate(request):
        if len(settings.device_secret) < 32:
            return error(503, 'not_configured')
        supplied = request.headers.get('x-device-secret', '').encode()
        if len(supplied) > 1024 or not hmac.compare_digest(supplied, settings.device_secret.encode()):
            return error(401, 'unauthorized')
        return None

    @app.get('/health')
    @app.get('/healthz')  # Legacy/local compatibility; Cloud Run reserves some z-ending paths.
    async def health():
        return {'ok': True}

    @app.get('/ready')
    @app.get('/readyz')
    async def ready():
        # Configuration readiness only. No billable provider probes on health checks.
        return JSONResponse({'configured': bool(configured())}, status_code=200 if configured() else 503)

    @app.delete('/v2/turn/{identifier}')
    async def cancel(identifier: str, request: Request):
        denied = authenticate(request)
        if denied:
            return denied
        try:
            identifier = str(uuid.UUID(identifier))
        except ValueError:
            return error(400, 'invalid_request_id')
        task = active.get(identifier)
        if task:
            task.cancel()
        return Response(status_code=204, headers={'Cache-Control': 'no-store'})

    async def admit_turn(identifier):
        now = time.monotonic()
        while admissions and admissions[0] <= now - 86400:
            admissions.popleft()
        if (len(admissions) >= settings.requests_per_day
                or sum(stamp > now - 60 for stamp in admissions) >= settings.requests_per_minute):
            raise QuotaDenied('minute_or_day')
        admissions.append(now)
        if settings.durable_quotas_required and quota is None:
            raise QuotaUnavailable()
        if quota is not None:
            await quota.admit(identifier)

    async def process(request, identifier, profile):
        if request.url.path == '/v3/notice':
            await admit_turn(identifier)
            speech = await backend.synthesize(NOTICE_TEXT)
            try:
                if len(speech) > MAX_OUTPUT_BYTES:
                    raise ValueError('oversized notice')
                pcm_frames(speech, max_seconds=47)
            except ValueError as failure:
                raise UpstreamError('tts') from failure
            return '', Answer(NOTICE_TEXT, []), speech, {}
        body = bytearray()
        try:
            async for chunk in request.stream():
                if len(body) + len(chunk) > MAX_INPUT_BYTES:
                    return error(413, 'audio_too_large', identifier)
                body.extend(chunk)
            frames = pcm_frames(bytes(body))
        except ClientDisconnect:
            return error(499, 'client_disconnected', identifier)
        except ValueError:
            return error(422, 'invalid_audio', identifier)
        if too_quiet_or_short(frames):
            return None
        await admit_turn(identifier)
        return await run_turn(backend, bytes(body), profile == 'private')

    @app.post('/v1/turn')
    @app.post('/v2/turn')
    @app.post('/v3/turn')
    @app.post('/v3/notice')
    async def turn(request: Request):
        denied = authenticate(request)
        if denied:
            return denied
        identifier = request.headers.get('x-request-id', str(uuid.uuid4()))
        try:
            identifier = str(uuid.UUID(identifier))
        except ValueError:
            return error(400, 'invalid_request_id')
        if not configured():
            return error(503, 'not_configured', identifier)
        profile = request.headers.get('x-profile', 'private')
        if profile not in ('private', 'playground'):
            return error(400, 'invalid_profile', identifier)
        notice = request.url.path == '/v3/notice'
        if profile == 'private' and not settings.private_approved and not notice:
            return error(503, 'private_route_unavailable', identifier)
        if not notice and request.headers.get('content-type', '').split(';')[0].lower() != 'audio/wav':
            return error(415, 'expected_audio_wav', identifier)
        if active:
            return error(429, 'device_busy', identifier)
        now = time.monotonic()
        for old in [key for key, expires in recent.items() if expires <= now]:
            del recent[old]
        if identifier in recent:
            return error(409, 'duplicate_request', identifier)
        if len(recent) >= 256:
            # Never trade an unexpired replay guarantee for new traffic, even silent/invalid uploads.
            return error(429, 'replay_cache_full', identifier)
        recent[identifier] = now + 600
        # Reserve ID and device before the first await, including the upload phase.
        task = asyncio.create_task(process(request, identifier, profile))
        active[identifier] = task
        try:
            result = await asyncio.wait_for(task, timeout=settings.turn_timeout)
            if isinstance(result, Response):
                return result
            if result is None:
                return Response(status_code=204, headers={'Cache-Control': 'no-store'})
            transcript, answer, speech, timings = result
            log.info('turn_completed id=%s timings=%s audio_bytes=%d', identifier, timings, len(speech))
            headers = {'Cache-Control': 'no-store', 'X-Request-ID': identifier}
            if request.url.path == '/v1/turn':
                return Response(speech, media_type='audio/wav', headers=headers)
            if request.url.path in ('/v3/turn', '/v3/notice'):
                metadata = json.dumps({
                    'version': 3, 'request_id': identifier, 'profile': profile,
                    'transcript': transcript, 'answer': answer.text, 'sources': answer.sources,
                    'timings': timings,
                }, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
                if len(metadata) > 16384:
                    raise UpstreamError('llm')
                envelope = struct.pack('<4sII', b'M5R3', len(metadata), len(speech))
                return Response(envelope + metadata + speech,
                                media_type='application/vnd.m5stack.turn+wav', headers=headers)
            return JSONResponse({
                'version': 2, 'request_id': identifier, 'profile': profile,
                'transcript': transcript, 'answer': answer.text, 'sources': answer.sources,
                'audio': {'mime_type': 'audio/wav', 'base64': base64.b64encode(speech).decode('ascii')},
                'timings': timings,
            }, headers=headers)
        except asyncio.TimeoutError:
            return error(504, 'turn_timeout', identifier)
        except asyncio.CancelledError:
            return error(409, 'turn_cancelled', identifier)
        except QuotaDenied as failure:
            return error(409 if failure.reason == 'duplicate' else 429,
                         'duplicate_request' if failure.reason == 'duplicate' else 'request_limit', identifier)
        except QuotaUnavailable:
            return error(503, 'quota_unavailable', identifier)
        except UpstreamError as failure:
            log.warning('upstream_failed id=%s stage=%s', identifier, failure.stage)
            return error(502, 'upstream_unavailable', identifier, failure.stage)
        except Exception:
            # Do not log exception messages or traceback locals containing user/provider payloads.
            log.error('turn_failed id=%s', identifier)
            return error(502, 'turn_failed', identifier)
        finally:
            active.pop(identifier, None)
    return app


def default_app():
    from .providers import HTTPProviders
    settings = Settings.from_env()
    quota = FirestoreQuota(settings.google_project) if settings.durable_quotas_required else None
    return create_app(settings, HTTPProviders(settings), quota=quota)
