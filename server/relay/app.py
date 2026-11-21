import asyncio
import base64
import hmac
import logging
import time
import uuid
from collections import deque

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from starlette.requests import ClientDisconnect

from .audio import MAX_INPUT_BYTES, pcm_frames, too_quiet_or_short
from .config import Settings
from .service import UpstreamError, run_turn

log = logging.getLogger('relay')


def create_app(settings: Settings, backend) -> FastAPI:
    app = FastAPI(title='Hebrew CoreS3 relay', docs_url=None, redoc_url=None)
    active = {}
    recent = {}
    admissions = deque()

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
        return JSONResponse({'configured': bool(settings.ready)}, status_code=200 if settings.ready else 503)

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

    async def process(request, identifier, profile):
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
        now = time.monotonic()
        while admissions and admissions[0] <= now - 86400:
            admissions.popleft()
        if (len(admissions) >= settings.requests_per_day
                or sum(stamp > now - 60 for stamp in admissions) >= settings.requests_per_minute):
            return error(429, 'local_request_limit', identifier)
        admissions.append(now)
        return await run_turn(backend, bytes(body), profile == 'private')

    @app.post('/v1/turn')
    @app.post('/v2/turn')
    async def turn(request: Request):
        denied = authenticate(request)
        if denied:
            return denied
        identifier = request.headers.get('x-request-id', str(uuid.uuid4()))
        try:
            identifier = str(uuid.UUID(identifier))
        except ValueError:
            return error(400, 'invalid_request_id')
        if not settings.ready:
            return error(503, 'not_configured', identifier)
        profile = request.headers.get('x-profile', 'private')
        if profile not in ('private', 'playground'):
            return error(400, 'invalid_profile', identifier)
        if profile == 'private' and not settings.private_approved:
            return error(503, 'private_route_unavailable', identifier)
        if request.headers.get('content-type', '').split(';')[0].lower() != 'audio/wav':
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
    return create_app(settings, HTTPProviders(settings))
