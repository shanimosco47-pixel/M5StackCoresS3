"""Operator-run hidden input. Creates new Secret Manager versions without files or shell-history keys.

This stores credentials only; live API/model validation is required before enabling voice service.
It does not enable public access or approve provider privacy policy automatically.
"""
import argparse
import getpass
from pathlib import Path
import re
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', args.project):
        parser.error('invalid project ID')
    if not sys.stdin.isatty():
        raise SystemExit('Run this helper in your own interactive terminal; refusing an unprotected key prompt')
    executable = shutil.which('gcloud')
    if not executable:
        raise SystemExit('gcloud is required')
    if Path(executable).resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise SystemExit('Refusing a repository-local gcloud executable; use the installed Google Cloud SDK')
    for name, label in (('groq', 'Groq'), ('openrouter', 'OpenRouter'),
                        ('azure', 'Azure Speech'), ('tavily', 'Tavily')):
        value = getpass.getpass(label + ' key (blank skips): ').strip()
        if not value:
            print('Skipped:', label)
            continue
        if '\r' in value or '\n' in value or len(value) > 4096:
            raise SystemExit('invalid credential format')
        result = subprocess.run([executable, 'secrets', 'versions', 'add', 'voice-relay-' + name,
                                 '--data-file=-', '--project=' + args.project, '--quiet'],
                                input=value.encode(), capture_output=True)
        value = ''
        if result.returncode:
            raise SystemExit('Secret upload failed for ' + label + '; credential not displayed')
        print('Stored new secret version:', label, '(value not displayed)')


if __name__ == '__main__':
    main()
