$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'remote-dev.ps1'

# Status only loads the script functions and performs no remote operation.
. $scriptPath Status
$config = @{
    REMOTE_HOST = '111.229.152.122'
    REMOTE_SSH_USER = 'ubuntu'
    SSH_KEY_PATH = ''
}
$postgres = Get-RemotePostgres $config
if ($postgres.Id -notmatch '^[a-f0-9]{12,64}$') { throw 'Unexpected container ID.' }
if ($postgres.Ip -notmatch '^\d{1,3}(\.\d{1,3}){3}$') { throw 'Unexpected PostgreSQL IPv4.' }
Write-Host "remote-dev read-only discovery: PASS container=$($postgres.Id) network=macrolens_default ip=$($postgres.Ip)"
