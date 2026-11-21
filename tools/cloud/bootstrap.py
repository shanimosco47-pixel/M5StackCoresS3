"""Create scoped cost controls and private secret containers using the operator's gcloud login.

No access tokens, device secrets or provider values are written to disk or printed.
This does not deploy a service, enable public access, or provision provider accounts.
"""
import argparse
import json
from decimal import Decimal
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request


def filters_match(actual, expected):
    # Empty filters and the documented credit-policy default do not narrow scope.
    # Compare the entire filter, so a same-named budget cannot hide extra restrictions.
    defaults = {'creditTypesTreatment': 'INCLUDE_ALL_CREDITS', 'services': [],
                'subaccounts': [], 'labels': {}, 'creditTypes': [], 'resourceAncestors': []}
    return defaults | actual == defaults | expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--billing-account', required=True)
    parser.add_argument('--cap', type=Decimal, required=True, help='Monthly Cloud Run cap in account currency')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', args.project):
        parser.error('invalid project ID')
    if not re.fullmatch(r'[A-F0-9]{6}-[A-F0-9]{6}-[A-F0-9]{6}', args.billing_account):
        parser.error('invalid billing account ID')
    if not args.cap.is_finite() or not Decimal('0') < args.cap <= Decimal('100'):
        parser.error('cap must be between 0 and 100 account-currency units')
    executable = shutil.which('gcloud')
    if not executable:
        raise SystemExit('gcloud is required')
    if Path(executable).resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise SystemExit('Refusing a repository-local gcloud executable; use the installed Google Cloud SDK')

    def gcloud(*command, data=None, check=True):
        result = subprocess.run([executable, *command, '--project=' + args.project, '--quiet'],
                                input=data, capture_output=True)
        if check and result.returncode:
            raise SystemExit('gcloud operation failed: ' + ' '.join(command[:3]) +
                             '\n' + result.stderr.decode('utf-8', errors='replace')[:600])
        return result

    def metadata(*command):
        return json.loads(gcloud(*command, '--format=json').stdout)

    project = metadata('projects', 'describe', args.project)
    number = project['projectNumber']
    billing = metadata('billing', 'projects', 'describe', args.project)
    if (not billing.get('billingEnabled')
            or billing.get('billingAccountName') != 'billingAccounts/' + args.billing_account):
        raise SystemExit('project must already be linked to the selected active billing account')
    # Normal SDK credential use; the access token remains inside this process.
    token = gcloud('auth', 'print-access-token').stdout.decode().strip()

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(NoRedirect)

    def api(method, url, payload=None):
        target = urllib.parse.urlsplit(url)
        if (target.scheme != 'https' or target.hostname not in
                ('cloudbilling.googleapis.com', 'billingbudgets.googleapis.com')
                or target.username or target.password or target.port not in (None, 443)):
            raise SystemExit('Refusing a non-Google HTTPS budget endpoint')
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(url, data=body, method=method, headers={
            'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
            'X-Goog-User-Project': args.project,
        })
        try:
            with opener.open(request, timeout=45) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            # Do not print request headers or arbitrary response bodies.
            try:
                detail = json.load(error).get('error', {})
                reasons = [item.get('reason', '') for item in detail.get('details', [])]
            except (ValueError, AttributeError):
                reasons = []
            raise SystemExit(f'Google API operation failed: HTTP{error.code}, {method}, '
                             f'{url.split("?")[0]}, reasons={reasons}') from None

    account = api('GET', 'https://cloudbilling.googleapis.com/v1/billingAccounts/' + args.billing_account)
    currency = account.get('currencyCode')
    if not account.get('open') or not currency:
        raise SystemExit('billing account must be open and report its currency')
    base = 'https://billingbudgets.googleapis.com/v1/billingAccounts/' + args.billing_account + '/budgets'
    budgets = api('GET', base).get('budgets', [])
    amount = {'currencyCode': currency, 'units': str(int(args.cap)),
              'nanos': int((args.cap % 1) * 1_000_000_000)}
    common = {
        'budgetFilter': {'projects': ['projects/' + number], 'calendarPeriod': 'MONTH'},
        'amount': {'specifiedAmount': amount},
        'thresholdRules': [{'thresholdPercent': n, 'spendBasis': 'CURRENT_SPEND'} for n in (0.5, 0.8, 1.0)],
        'notificationsRule': {'enableProjectLevelRecipients': True, 'disableDefaultIamRecipients': False},
    }
    cap = dict(common, displayName='M5Stack Cloud Run cap ' + args.project,
               budgetFilter=dict(common['budgetFilter'], services=['services/152E-C115-5142'],
                                 creditTypesTreatment='EXCLUDE_ALL_CREDITS'),
               spendCap={'inputState': 'CONFIGURED'})
    total_alert = dict(common, displayName='M5Stack total-cost alert ' + args.project)

    def ensure_budget(payload):
        existing = next((item for item in budgets if item.get('displayName') == payload['displayName']), None)
        if existing:
            current_amount = existing.get('amount', {}).get('specifiedAmount', {})
            actual = Decimal(current_amount.get('units', '0')) + Decimal(current_amount.get('nanos', 0)) / 1_000_000_000
            scope_matches = filters_match(existing.get('budgetFilter', {}), payload['budgetFilter'])
            if not scope_matches or actual != args.cap or current_amount.get('currencyCode') != currency:
                raise SystemExit('Existing named budget differs; inspect it rather than overwrite it')
            return existing
        return api('POST', base, payload)

    result = ensure_budget(cap)
    result = api('GET', 'https://billingbudgets.googleapis.com/v1/' + result['name'])
    if result.get('spendCap', {}).get('outputState') != 'CONFIGURED':
        raise SystemExit('Spend cap is not yet verified active; stopped before secret provisioning')
    ensure_budget(total_alert)
    print(json.dumps({'project': args.project, 'cloud_run_cap': str(args.cap), 'currency': currency,
                      'cap_state': 'CONFIGURED', 'total_cost_alert': str(args.cap)}))
    runtime = 'serviceAccount:m5-voice-runtime@' + args.project + '.iam.gserviceaccount.com'
    for name in ('device-secret', 'groq', 'openrouter', 'azure', 'tavily'):
        secret_id = 'voice-relay-' + name
        if gcloud('secrets', 'describe', secret_id, check=False).returncode:
            gcloud('secrets', 'create', secret_id, '--replication-policy=automatic')
        gcloud('secrets', 'add-iam-policy-binding', secret_id, '--member=' + runtime,
               '--role=roles/secretmanager.secretAccessor', '--condition=None')
        if name == 'device-secret':
            versions = metadata('secrets', 'versions', 'list', secret_id, '--filter=state=ENABLED')
            if not versions:
                gcloud('secrets', 'versions', 'add', secret_id, '--data-file=-',
                       data=secrets.token_urlsafe(32).encode())
        print('Prepared secret container:', secret_id, '(value not displayed)')


if __name__ == '__main__':
    main()
