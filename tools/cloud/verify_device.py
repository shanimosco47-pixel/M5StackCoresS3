"""Verify direct device authentication without invoking STT, LLM, search or TTS."""
import argparse
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
import wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--region', default='europe-west1')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', args.project):
        parser.error('invalid project')
    cli = shutil.which('gcloud')
    if not cli or Path(cli).resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise SystemExit('Use the installed Google Cloud SDK')

    def sdk(*command):
        result = subprocess.run([cli, *command, '--project=' + args.project, '--quiet'],
                                capture_output=True, timeout=60)
        if result.returncode:
            raise SystemExit('Cloud metadata or device-secret access failed; values not displayed')
        return result.stdout.decode().strip()

    service = json.loads(sdk('run', 'services', 'describe', 'voice-relay',
                             '--region=' + args.region, '--format=json'))
    container = service['spec']['template']['spec']['containers'][0]
    flags = {entry['name']: entry.get('value') for entry in container.get('env', [])}
    if flags.get('DURABLE_QUOTAS_REQUIRED') != 'true' or flags.get('GOOGLE_CLOUD_PROJECT') != args.project:
        raise SystemExit('Direct device service must require durable quotas in this project')
    url = service['status']['url']
    target = urllib.parse.urlsplit(url)
    if (target.scheme != 'https' or not target.hostname or not target.hostname.endswith('.run.app')
            or target.username or target.password or target.port not in (None, 443)):
        raise SystemExit('Refusing an unexpected service endpoint')
    secret = sdk('secrets', 'versions', 'access', '1', '--secret=voice-relay-device-secret')
    if not 32 <= len(secret) <= 256 or any(ord(c) < 33 or ord(c) > 126 for c in secret):
        raise SystemExit('Invalid device credential format')

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = urllib.request.build_opener(NoRedirect)

    def request(path, headers=None, body=None):
        req = urllib.request.Request(url + path, headers=headers or {}, data=body)
        try:
            response = opener.open(req, timeout=45)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            payload = response.read(65537)
            if len(payload) > 65536:
                raise SystemExit('Oversized diagnostic response')
            return response.code, payload

    audio = io.BytesIO()
    with wave.open(audio, 'wb') as stream:
        stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        stream.writeframes(b'\0' * 19200)
    identifier = str(uuid.uuid4())
    headers = {'Content-Type': 'audio/wav', 'X-Request-ID': identifier}
    health = request('/health')
    ready = request('/ready')
    denied = request('/v3/turn', headers, audio.getvalue())
    accepted = request('/v3/turn', headers | {'X-Device-Secret': secret}, audio.getvalue())
    if (health[0] != 200 or json.loads(health[1]) != {'ok': True}
            or ready[0] != 200 or json.loads(ready[1]) != {'configured': True}
            or denied[0] != 401 or accepted[0] != 204):
        raise SystemExit(json.dumps({'verification': 'failed', 'health': health[0], 'ready': ready[0],
                                     'missing_secret': denied[0], 'authenticated_silence': accepted[0]}))
    print(json.dumps({'verification': 'passed', 'revision': service['status']['latestReadyRevisionName'],
                      'health': 200, 'ready': 200, 'missing_secret': 401,
                      'authenticated_silence': 204, 'provider_calls': 0,
                      'durable_quotas_required': True}))


if __name__ == '__main__':
    main()
