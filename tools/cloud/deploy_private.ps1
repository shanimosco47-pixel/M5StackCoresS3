param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z][a-z0-9-]{4,28}[a-z0-9]$')]
    [string]$ProjectId,
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-F0-9]{6}-[A-F0-9]{6}-[A-F0-9]{6}$')]
    [string]$BillingAccountId,
    [ValidateRange(0.01, 100)]
    [decimal]$CloudRunMonthlyCap = 5,
    [string]$Region = 'europe-west1'
)
$ErrorActionPreference = 'Stop'
$m5RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$m5ServerRoot = Join-Path $m5RepositoryRoot 'server'
$m5SourceCommit = (git -C $m5RepositoryRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'Cannot identify the source commit.' }

# Verify the actual spend cap and scoped secret setup before starting any build.
$m5CapArgument = $CloudRunMonthlyCap.ToString([Globalization.CultureInfo]::InvariantCulture)
& python (Join-Path $PSScriptRoot 'bootstrap.py') "--project=$ProjectId" "--billing-account=$BillingAccountId" "--cap=$m5CapArgument"
if ($LASTEXITCODE -ne 0) { throw 'Cost-control verification failed; deployment was not started.' }
# Source upload uses server/.gcloudignore: no credentials, tests, local files or firmware images.
$m5DeployArgs = @(
    'run', 'deploy', 'voice-relay',
    "--source=$m5ServerRoot", "--project=$ProjectId", "--region=$Region",
    "--service-account=m5-voice-runtime@$ProjectId.iam.gserviceaccount.com",
    "--build-service-account=projects/$ProjectId/serviceAccounts/m5-voice-builder@$ProjectId.iam.gserviceaccount.com",
    '--no-allow-unauthenticated', '--min-instances=0', '--max-instances=1',
    '--concurrency=4', '--cpu=1', '--memory=256Mi', '--timeout=60',
    '--set-secrets=DEVICE_SECRET=voice-relay-device-secret:latest',
    '--set-env-vars=PRIVATE_PROVIDERS_APPROVED=false,REQUESTS_PER_MINUTE=6,REQUESTS_PER_DAY=100',
    "--labels=source-commit=$m5SourceCommit", '--quiet',
    '--format=value(status.url)'
)
& gcloud @m5DeployArgs
if ($LASTEXITCODE -ne 0) { throw 'Private Cloud Run deployment failed. Inspect cloud build diagnostics.' }
