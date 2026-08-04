$ErrorActionPreference = 'Stop'
$scriptPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'remote-dev.ps1'
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

$tokens = $null
$errors = $null
[Management.Automation.Language.Parser]::ParseFile($scriptPath, [ref]$tokens, [ref]$errors) | Out-Null
if ($errors.Count) { throw ($errors | ForEach-Object Message | Out-String) }

$source = [IO.File]::ReadAllText($scriptPath)
@(
    'Provision', 'Start', 'Status', 'Stop', 'Deprovision',
    'BatchMode=yes', 'StrictHostKeyChecking=yes', 'ExitOnForwardFailure=yes',
    'ServerAliveInterval=30', "'-N', '-T', '-L'", '127.0.0.1:',
    'sudo docker ps', 'sudo docker inspect', 'sudo docker exec',
    '{{range $name, $network := .NetworkSettings.Networks}}', 'Get-MacrolensNetworkIp',
    'com.docker.compose.project=macrolens', 'com.docker.compose.service=postgres',
    'health=healthy', 'macrolens_default', 'LOCAL_JWT_SECRET', '$env:JWT_SECRET',
    "Join-Path `$Root '.venv'", 'Node.js 22', '.cache\codex-runtimes', 'local-preview-server\.mjs',
    'commandLineSha256', 'Get-CimInstance Win32_Process', 'WindowStyle Hidden',
    'CONNECTION LIMIT 20', 'NOSUPERUSER', 'NOCREATEDB', 'NOCREATEROLE',
    'NOINHERIT', 'NOREPLICATION', 'NOBYPASSRLS',
    'GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app',
    'GRANT SELECT, INSERT ON TABLE audit.audit_log',
    'REVOKE INSERT, UPDATE, DELETE ON TABLE data.observation_vintage',
    'pg_auth_members', 'pg_database', 'pg_namespace', 'pg_proc',
    'Remove-KnownPreviewServer -ValidateOnly', 'Test-PythonRuntimeDependencies',
    'Ensure-PythonRuntimeDependencies', "`$ErrorActionPreference = 'Continue'",
    'Get-PipFailureCategory', 'Invoke-PipInstall', "'--timeout', '60'",
    "'--retries', '5'", "'--no-input'"
) | ForEach-Object {
    if (-not $source.Contains($_)) { throw "Missing contract: $_" }
}

if ($source.Contains('5432:5432')) { throw 'Public PostgreSQL mapping forbidden.' }
if ($source -match 'index\s+\.NetworkSettings\.Networks') { throw 'Quoted network index template is forbidden on Windows OpenSSH.' }
$templateLine = @($source -split "`n" | Where-Object { $_ -match '^\s*\$inspectTemplate\s*=' })
if ($templateLine.Count -ne 1 -or $templateLine[0].Contains('"')) { throw 'Inspect template must not contain nested double quotes.' }
if ($source -match '(?im)^\s*ALTER\s+DEFAULT\s+PRIVILEGES') { throw 'Default privilege mutation forbidden.' }
if ($source -match '(?im)^\s*GRANT\s+ALL') { throw 'GRANT ALL forbidden.' }
if ($source -match '(?im)^\s*GRANT[^;]*\bTRUNCATE\b') { throw 'TRUNCATE grant forbidden.' }
if ($source -match '(?im)^\s*GRANT[^;]*data\.observation_vintage') { throw 'observation_vintage write grant forbidden.' }
if ($source.Contains('& $python -c ''import asyncpg, psycopg, uvicorn''')) { throw 'Direct native dependency import probe is forbidden under global EAP Stop.' }

& git.exe -C $repoRoot check-ignore --quiet .env.remote
if ($LASTEXITCODE -ne 0) { throw '.env.remote must be gitignored.' }
& git.exe -C $repoRoot check-ignore --quiet .env.remote.state.json
if ($LASTEXITCODE -ne 0) { throw '.env.remote.state.json must be gitignored.' }

# Load functions through the read-only Status action, then exercise local-only discovery and PID identity checks.
. $scriptPath Status
$validNetworkIp = Get-MacrolensNetworkIp "bridge=172.17.0.2`nmacrolens_default=172.19.0.4"
if ($validNetworkIp -ne '172.19.0.4') { throw 'Expected exact macrolens_default IPv4 parsing.' }
try {
    Get-MacrolensNetworkIp "macrolens_default=172.19.0.4`nmacrolens_default=172.19.0.5" | Out-Null
    throw 'Duplicate macrolens_default rows must fail closed.'
} catch {
    if ($_.Exception.Message -eq 'Duplicate macrolens_default rows must fail closed.') { throw }
}
try {
    Get-MacrolensNetworkIp 'macrolens_default=999.19.0.4' | Out-Null
    throw 'Invalid IPv4 must fail closed.'
} catch {
    if ($_.Exception.Message -eq 'Invalid IPv4 must fail closed.') { throw }
}
$node22 = Find-Node22
if (-not [IO.Path]::IsPathRooted($node22)) { throw 'Node 22 discovery must return an absolute path.' }
$python312 = Find-Python312Bootstrap
if (-not [IO.Path]::IsPathRooted($python312)) { throw 'Python 3.12 discovery must return an absolute path.' }

$dependencyTestRoot = Join-Path ([IO.Path]::GetTempPath()) ("macrolens-r2-" + [Guid]::NewGuid().ToString('N'))
$missingProbe = Join-Path $dependencyTestRoot 'missing.cmd'
$unexpectedProbe = Join-Path $dependencyTestRoot 'unexpected.cmd'
$checkedSuccess = Join-Path $dependencyTestRoot 'checked-success.cmd'
$checkedFailure = Join-Path $dependencyTestRoot 'checked-failure.cmd'
New-Item -ItemType Directory -Path $dependencyTestRoot | Out-Null
try {
    [IO.File]::WriteAllText($missingProbe, "@echo off`r`nexit /b 3`r`n")
    [IO.File]::WriteAllText($unexpectedProbe, "@echo off`r`n>&2 echo unexpected probe failure`r`nexit /b 7`r`n")
    [IO.File]::WriteAllText($checkedSuccess, "@echo off`r`necho success-stdout`r`n>&2 echo success-stderr`r`nexit /b 0`r`n")
    [IO.File]::WriteAllText($checkedFailure, "@echo off`r`n>&2 echo secret-canary-must-not-leak`r`nexit /b 7`r`n")

    $checkedOutput = Invoke-Checked $checkedSuccess @()
    if ($checkedOutput -notmatch 'success-stdout' -or $checkedOutput -notmatch 'success-stderr') { throw 'Successful native output must include stdout and stderr.' }
    if ($ErrorActionPreference -ne 'Stop') { throw 'Invoke-Checked must restore EAP after success.' }
    try {
        Invoke-Checked $checkedFailure @() | Out-Null
        throw 'Nonzero native command must fail.'
    } catch {
        if ($_.Exception.Message -eq 'Nonzero native command must fail.') { throw }
        if ($_.Exception.Message -notmatch 'checked-failure\.cmd exited with code 7') { throw }
        if ($_.Exception.Message -match 'secret-canary-must-not-leak') { throw 'Generic native failure leaked captured output.' }
    }
    if ($ErrorActionPreference -ne 'Stop') { throw 'Invoke-Checked must restore EAP after failure.' }

    $pipCategory = Get-PipFailureCategory @('https://user:password@example.invalid REMOTE_DB_PASSWORD=secret ReadTimeout')
    if ($pipCategory -ne 'network') { throw 'Pip diagnostics must return a bounded non-secret category.' }
    $installEvents = New-Object Collections.Generic.List[string]
    $installed = Ensure-PythonRuntimeDependencies $missingProbe { $installEvents.Add('installed') }
    if (-not $installed -or $installEvents.Count -ne 1) { throw 'Missing dependencies must select the install branch exactly once.' }
    if ($ErrorActionPreference -ne 'Stop') { throw 'Dependency probe must restore ErrorActionPreference.' }

    $unexpectedEvents = New-Object Collections.Generic.List[string]
    try {
        Ensure-PythonRuntimeDependencies $unexpectedProbe { $unexpectedEvents.Add('installed') } | Out-Null
        throw 'Unexpected dependency probe failures must fail closed.'
    } catch {
        if ($_.Exception.Message -eq 'Unexpected dependency probe failures must fail closed.') { throw }
        if ($_.Exception.Message -notmatch 'exit code 7') { throw }
    }
    if ($unexpectedEvents.Count -ne 0) { throw 'Unexpected probe failures must not install dependencies.' }
} finally {
    if (Test-Path -LiteralPath $missingProbe) { Remove-Item -LiteralPath $missingProbe -Force }
    if (Test-Path -LiteralPath $unexpectedProbe) { Remove-Item -LiteralPath $unexpectedProbe -Force }
    if (Test-Path -LiteralPath $checkedSuccess) { Remove-Item -LiteralPath $checkedSuccess -Force }
    if (Test-Path -LiteralPath $checkedFailure) { Remove-Item -LiteralPath $checkedFailure -Force }
    if (Test-Path -LiteralPath $dependencyTestRoot) { Remove-Item -LiteralPath $dependencyTestRoot -Force }
}

$probe = $null
try {
    $probe = Start-Process -FilePath powershell.exe -ArgumentList @('-NoProfile', '-Command', 'Start-Sleep -Seconds 30; # macrolens-process-record-test') -PassThru -WindowStyle Hidden
    Start-Sleep -Milliseconds 300
    $record = New-ProcessRecord $probe 'test' 'macrolens-process-record-test'
    if (-not (Test-ProcessRecord $record)) { throw 'Exact process identity should match.' }
    $record.commandLineSha256 = ('0' * 64)
    if (Test-ProcessRecord $record) { throw 'Tampered command-line hash must not match.' }
} finally {
    if ($probe -and -not $probe.HasExited) { Stop-Process -Id $probe.Id -Force }
}

Write-Host 'remote-dev static and local process-safety contract: PASS'
