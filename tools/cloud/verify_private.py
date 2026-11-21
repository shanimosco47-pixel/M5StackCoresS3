"""Check the live private staging service, without reading device/provider secrets."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--region', default='europe-west1')
    parser.add_argument('--configured', action='store_true', help='Expect configured staging, not missing settings')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', args.project):
        parser.error('invalid project ID')
    cli = shutil.which('gcloud')
    if not cli or Path(cli).resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise SystemExit('An installed Google Cloud SDK outside the repository is required')

    def run(*command):
        return subprocess.check_output([cli, *command, '--project=' + args.project, '--quiet'], text=True)

    service = json.loads(run('run', 'services', 'describe', 'voice-relay',
                             '--region=' + args.region, '--format=json'))
    policy = json.loads(run('run', 'services', 'get-iam-policy', 'voice-relay',
                            '--region=' + args.region, '--format=json'))
    if any(member in ('allUsers', 'allAuthenticatedUsers')
           for binding in policy.get('bindings', []) for member in binding.get('members', [])):
        raise SystemExit('Service has broad public IAM access; private staging verification failed')
    url = service['status']['url']
    target = urllib.parse.urlsplit(url)
    if (target.scheme != 'https' or not target.hostname or not target.hostname.endswith('.run.app')
            or target.username or target.password or target.port not in (None, 443)):
        raise SystemExit('Refusing a non-Cloud-Run HTTPS service URL')
    token = run('auth', 'print-identity-token').strip()

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)

    def probe(path, authenticated):
        headers = {'Authorization': 'Bearer ' + token} if authenticated else {}
        request = urllib.request.Request(url + path, headers=headers)
        try:
            response = opener.open(request, timeout=45)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = json.load(response) if 'application/json' in response.headers.get('Content-Type', '') else None
            return response.code, body

    public = probe('/health', False)
    health = probe('/health', True)
    ready = probe('/ready', True)
    expected_ready = (200, {'configured': True}) if args.configured else (503, {'configured': False})
    if public[0] not in (401, 403, 404) or health != (200, {'ok': True}) or ready != expected_ready:
        raise SystemExit(json.dumps({'verification': 'failed', 'anonymous_status': public[0],
                                     'health': health, 'readiness': ready}))
    print(json.dumps({'verification': 'passed', 'url': url,
                      'revision': service['status']['latestReadyRevisionName'],
                      'anonymous_status': public[0], 'health': health, 'readiness': ready,
                      'public_access': False}))


if __name__ == '__main__':
    main()
