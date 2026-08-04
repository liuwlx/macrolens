[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('Provision', 'Start', 'Status', 'Stop', 'Deprovision')]
    [string]$Action,

    [ValidateSet('Demo', 'Live')]
    [string]$DataMode = 'Demo'
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$Root = Split-Path -Parent $PSScriptRoot
$Secret = Join-Path $Root '.env.remote'
$State = Join-Path $Root '.env.remote.state.json'
$HostName = '111.229.152.122'
$SshUser = 'ubuntu'
$Role = 'macrolens_local_dev'
$Schemas = @('source', 'catalog', 'ingestion', 'data', 'release', 'docs', 'fomc', 'app', 'audit')

if ($Action -ne 'Start' -and $PSBoundParameters.ContainsKey('DataMode')) {
    throw '-DataMode is only valid with the Start action.'
}

function Assert-LastExitCode([string]$Name) {
    if ($LASTEXITCODE -ne 0) { throw "$Name exited with code $LASTEXITCODE." }
}

function Invoke-Checked([string]$File, [string[]]$Arguments, [string]$StandardInput = '') {
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        if ($StandardInput) { $output = $StandardInput | & $File @Arguments 2>&1 }
        else { $output = & $File @Arguments 2>&1 }
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -ne 0) {
        $executableName = [IO.Path]::GetFileName($File)
        throw "$executableName exited with code $exitCode."
    }
    return (($output | ForEach-Object { [string]$_ }) -join "`n").Trim()
}

function Resolve-Application([string]$Value) {
    if (Test-Path -LiteralPath $Value -PathType Leaf) {
        return (Resolve-Path -LiteralPath $Value).Path
    }
    $command = Get-Command $Value -CommandType Application -ErrorAction Stop | Select-Object -First 1
    return $command.Source
}

function Read-RemoteEnvironment {
    if (-not (Test-Path -LiteralPath $Secret)) { throw 'Run Provision first.' }
    $values = @{}
    Get-Content -LiteralPath $Secret | ForEach-Object {
        if ($_ -notmatch '^\s*(#|$)') {
            $pair = $_ -split '=', 2
            $values[$pair[0]] = $pair[1]
        }
    }
    @(
        'REMOTE_HOST', 'REMOTE_SSH_USER', 'REMOTE_DB_NAME', 'REMOTE_DB_ADMIN_USER', 'REMOTE_DB_USER',
        'REMOTE_DB_PASSWORD', 'LOCAL_JWT_SECRET', 'LOCAL_DB_PORT', 'LOCAL_API_PORT',
        'LOCAL_WEB_PORT', 'PYTHON_BOOTSTRAP_EXE', 'NODE_EXE'
    ) | ForEach-Object {
        if (-not $values[$_]) { throw "Missing $_ in .env.remote." }
    }
    if ($values.REMOTE_HOST -ne $HostName -or $values.REMOTE_SSH_USER -ne $SshUser) {
        throw 'Unapproved remote target.'
    }
    return $values
}

function Assert-SqlIdentifier([string]$Value) {
    if ($Value -notmatch '^[a-z_][a-z0-9_]*$') { throw 'Invalid SQL identifier.' }
}

function Get-SshArguments($Config) {
    $arguments = @(
        '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=yes',
        '-o', 'ExitOnForwardFailure=yes',
        '-o', 'ServerAliveInterval=30',
        '-o', 'ServerAliveCountMax=3'
    )
    if ($Config.SSH_KEY_PATH) {
        $key = [Environment]::ExpandEnvironmentVariables($Config.SSH_KEY_PATH)
        if (-not (Test-Path -LiteralPath $key -PathType Leaf)) { throw 'SSH key missing.' }
        $arguments += @('-i', $key)
    }
    $arguments += "$($Config.REMOTE_SSH_USER)@$($Config.REMOTE_HOST)"
    return $arguments
}

function Invoke-Ssh([string]$Command, $Config, [string]$StandardInput = '') {
    $ssh = Resolve-Application 'ssh.exe'
    return Invoke-Checked $ssh (@(Get-SshArguments $Config) + @($Command)) $StandardInput
}

function Get-MacrolensNetworkIp([string]$InspectOutput) {
    $ips = @($InspectOutput -split "`n" | ForEach-Object {
        $line = $_.Trim()
        if ($line -match '^macrolens_default=(?<ip>\d{1,3}(?:\.\d{1,3}){3})$') { $matches.ip }
    })
    if ($ips.Count -ne 1) { throw 'Expected exactly one macrolens_default IPv4 address.' }
    $parsed = $null
    if (-not [Net.IPAddress]::TryParse($ips[0], [ref]$parsed) -or
        $parsed.AddressFamily -ne [Net.Sockets.AddressFamily]::InterNetwork -or
        $parsed.ToString() -ne $ips[0]) {
        throw 'macrolens_default did not contain a canonical IPv4 address.'
    }
    return $ips[0]
}

function Get-RemotePostgres($Config) {
    $find = "sudo docker ps --filter label=com.docker.compose.project=macrolens --filter label=com.docker.compose.service=postgres --filter health=healthy --filter network=macrolens_default --format '{{.ID}}'"
    $ids = @((Invoke-Ssh $find $Config) -split "`n" | Where-Object { $_ })
    if ($ids.Count -ne 1 -or $ids[0] -notmatch '^[a-f0-9]{12,64}$') {
        throw 'Expected exactly one healthy macrolens Compose postgres container on macrolens_default.'
    }
    $inspectTemplate = '{{range $name, $network := .NetworkSettings.Networks}}{{$name}}={{$network.IPAddress}}{{println}}{{end}}'
    $inspect = "sudo docker inspect -f '$inspectTemplate' $($ids[0])"
    $ip = Get-MacrolensNetworkIp (Invoke-Ssh $inspect $Config)
    return @{ Id = $ids[0]; Ip = $ip }
}

function Invoke-RemotePsql([string]$Sql, $Config, $Postgres) {
    Assert-SqlIdentifier $Config.REMOTE_DB_NAME
    Assert-SqlIdentifier $Config.REMOTE_DB_ADMIN_USER
    $command = "sudo docker exec -i $($Postgres.Id) psql -X -v ON_ERROR_STOP=1 -U $($Config.REMOTE_DB_ADMIN_USER) -d $($Config.REMOTE_DB_NAME)"
    Invoke-Ssh $command $Config $Sql | Out-Null
}

function New-Secret {
    $bytes = New-Object byte[] 32
    $random = [Security.Cryptography.RandomNumberGenerator]::Create()
    try { $random.GetBytes($bytes) } finally { $random.Dispose() }
    return ([Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_') + '!a9')
}

function Protect-SecretFile {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls.exe $Secret '/inheritance:r' '/grant:r' "${identity}:(F)" | Out-Null
    Assert-LastExitCode 'icacls.exe'
}

function Find-Node22 {
    $candidates = New-Object Collections.Generic.List[string]
    if ($env:MACROLENS_NODE22) { $candidates.Add($env:MACROLENS_NODE22) }
    try { $candidates.Add((Resolve-Application 'node.exe')) } catch {}
    if ($env:NVM_HOME) {
        Get-ChildItem -LiteralPath $env:NVM_HOME -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            $candidates.Add((Join-Path $_.FullName 'node.exe'))
        }
    }
    $runtimeCache = Join-Path $env:USERPROFILE '.cache\codex-runtimes'
    Get-ChildItem -LiteralPath $runtimeCache -Filter 'node.exe' -File -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
        $candidates.Add($_.FullName)
    }
    $playwright = Join-Path $env:LOCALAPPDATA 'ms-playwright-go'
    Get-ChildItem -LiteralPath $playwright -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $candidates.Add((Join-Path $_.FullName 'node.exe'))
    }
    $npx = Join-Path $env:LOCALAPPDATA 'npm-cache\_npx'
    Get-ChildItem -LiteralPath $npx -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $candidates.Add((Join-Path $_.FullName 'node_modules\node\bin\node.exe'))
    }
    foreach ($candidate in @($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        $resolved = (Resolve-Path -LiteralPath $candidate).Path
        $version = Invoke-Checked $resolved @('-p', 'process.versions.node')
        if (($version -split '\.')[0] -eq '22') { return $resolved }
    }
    throw 'Node.js 22 was not found. Set MACROLENS_NODE22 to an absolute node.exe path and retry Provision.'
}

function Find-Python312Bootstrap {
    foreach ($candidate in @('py.exe', 'python.exe')) {
        try {
            $resolved = Resolve-Application $candidate
            $prefix = @()
            if ([IO.Path]::GetFileName($resolved) -ieq 'py.exe') { $prefix = @('-3.12') }
            $version = Invoke-Checked $resolved ($prefix + @('-c', "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')"))
            if ($version -eq '3.12') { return $resolved }
        } catch {}
    }
    throw 'Python 3.12 was not found.'
}

function Provision-RemoteDevelopment {
    $node = Find-Node22
    $python = Find-Python312Bootstrap
    $config = @{
        REMOTE_HOST = $HostName
        REMOTE_SSH_USER = $SshUser
        REMOTE_DB_NAME = 'macrolens'
        REMOTE_DB_ADMIN_USER = 'macrolens'
        SSH_KEY_PATH = ''
    }
    $postgres = Get-RemotePostgres $config
    $password = New-Secret
    $jwtSecret = New-Secret
    $literalPassword = $password.Replace("'", "''")
    $schemaGrants = ($Schemas | ForEach-Object {
        "GRANT USAGE ON SCHEMA `"$_`" TO $Role; REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA `"$_`" FROM $Role; REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA `"$_`" FROM $Role; GRANT SELECT ON ALL TABLES IN SCHEMA `"$_`" TO $Role;"
    }) -join "`n"
    $sql = @"
BEGIN;
DO `$do`$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '$Role') THEN
        CREATE ROLE $Role LOGIN PASSWORD '$literalPassword';
    ELSE
        ALTER ROLE $Role PASSWORD '$literalPassword';
    END IF;
END `$do`$;
ALTER ROLE $Role CONNECTION LIMIT 20 NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS;
REVOKE CREATE ON SCHEMA public FROM $Role;
GRANT CONNECT ON DATABASE macrolens TO $Role;
$schemaGrants
GRANT USAGE ON SCHEMA public TO $Role;
GRANT SELECT ON TABLE public.alembic_version TO $Role;
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO $Role;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA app TO $Role;
REVOKE UPDATE, DELETE ON TABLE audit.audit_log FROM $Role;
GRANT SELECT, INSERT ON TABLE audit.audit_log TO $Role;
REVOKE INSERT, UPDATE, DELETE ON TABLE data.observation_vintage FROM $Role;
DO `$do`$ BEGIN
    IF has_schema_privilege('$Role', 'public', 'CREATE') THEN
        RAISE EXCEPTION 'public schema still grants CREATE through PUBLIC';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class WHERE relowner = (SELECT oid FROM pg_roles WHERE rolname = '$Role')) THEN
        RAISE EXCEPTION '$Role unexpectedly owns database objects';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_database WHERE datdba = (SELECT oid FROM pg_roles WHERE rolname = '$Role'))
       OR EXISTS (SELECT 1 FROM pg_namespace WHERE nspowner = (SELECT oid FROM pg_roles WHERE rolname = '$Role'))
       OR EXISTS (SELECT 1 FROM pg_proc WHERE proowner = (SELECT oid FROM pg_roles WHERE rolname = '$Role')) THEN
        RAISE EXCEPTION '$Role unexpectedly owns database, schema, or function objects';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_auth_members
        WHERE roleid = (SELECT oid FROM pg_roles WHERE rolname = '$Role')
           OR member = (SELECT oid FROM pg_roles WHERE rolname = '$Role')
    ) THEN
        RAISE EXCEPTION '$Role unexpectedly has role membership relationships';
    END IF;
END `$do`$;
COMMIT;
"@
    Invoke-RemotePsql $sql $config $postgres
    $lines = @(
        "REMOTE_HOST=$HostName", "REMOTE_SSH_USER=$SshUser", 'REMOTE_DB_NAME=macrolens',
        'REMOTE_DB_ADMIN_USER=macrolens', "REMOTE_DB_USER=$Role", "REMOTE_DB_PASSWORD=$password",
        "LOCAL_JWT_SECRET=$jwtSecret", 'SSH_KEY_PATH=', 'LOCAL_DB_PORT=15432',
        'LOCAL_API_PORT=8000', 'LOCAL_WEB_PORT=3000', "PYTHON_BOOTSTRAP_EXE=$python", "NODE_EXE=$node"
    )
    [IO.File]::WriteAllLines($Secret, $lines, (New-Object Text.UTF8Encoding($false)))
    Protect-SecretFile
    Write-Host 'Provisioned least-privilege local development role and protected .env.remote.'
}

function Test-Port([int]$Port) {
    $client = New-Object Net.Sockets.TcpClient
    try {
        $result = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        return ($result.AsyncWaitHandle.WaitOne(250) -and $client.Connected)
    } catch { return $false } finally { $client.Dispose() }
}

function Assert-PortFree([int]$Port) {
    if (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue) {
        throw "Port $Port is in use."
    }
}

function Remove-KnownPreviewServer([switch]$ValidateOnly) {
    $listeners = @(3000, 4010 | ForEach-Object {
        Get-NetTCPConnection -State Listen -LocalPort $_ -ErrorAction SilentlyContinue
    })
    if ($listeners.Count -eq 0) { return }
    $pids = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    if ($pids.Count -ne 1) { throw 'Ports 3000/4010 are occupied by unknown processes.' }
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$($pids[0])"
    $isNode = $process -and ([IO.Path]::GetFileName($process.ExecutablePath) -ieq 'node.exe')
    $isPreview = $process -and ($process.CommandLine -match '(?i)[\\/]artifacts[\\/]design-qa[\\/]local-preview-server\.mjs(?:"|\s|$)')
    $ownedPorts = @($listeners | Where-Object { $_.OwningProcess -eq $pids[0] } | Select-Object -ExpandProperty LocalPort -Unique)
    if (-not $isNode -or -not $isPreview -or $ownedPorts.Count -ne 2 -or $ownedPorts -notcontains 3000 -or $ownedPorts -notcontains 4010) {
        throw 'Ports 3000/4010 are occupied by an unrecognized process; refusing to stop it.'
    }
    if ($ValidateOnly) { return }
    & taskkill.exe /PID $pids[0] /T /F | Out-Null
    Assert-LastExitCode 'taskkill.exe'
    $deadline = (Get-Date).AddSeconds(10)
    while ((Get-Date) -lt $deadline -and ((Test-Port 3000) -or (Test-Port 4010))) { Start-Sleep -Milliseconds 200 }
    if ((Test-Port 3000) -or (Test-Port 4010)) { throw 'Known preview server did not release ports 3000/4010.' }
}

function Wait-ForPort([int]$Port, $Process, [int]$Seconds = 25) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if ($Process.HasExited) { throw "Process exited before port $Port opened." }
        if (Test-Port $Port) { return }
        Start-Sleep -Milliseconds 250
    }
    throw "Port $Port did not open before timeout."
}

function Test-PythonRuntimeDependencies([string]$Python) {
    $probe = "import importlib.util,sys;names=('asyncpg','psycopg','uvicorn');sys.exit(3 if any(importlib.util.find_spec(name) is None for name in names) else 0)"
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        # Windows PowerShell turns native stderr into ErrorRecord objects. Limit Continue to
        # this probe so the expected missing-module result cannot terminate the whole script.
        $ErrorActionPreference = 'Continue'
        $probeOutput = & $Python -c $probe 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -eq 0) { return $true }
    if ($exitCode -eq 3) { return $false }
    $outputPresent = @($probeOutput).Count -gt 0
    throw "Python dependency probe failed with exit code $exitCode (outputPresent=$outputPresent)."
}

function Get-PipFailureCategory([object[]]$Output) {
    $text = (($Output | ForEach-Object { [string]$_ }) -join "`n")
    if ($text -match '(?i)no space left|disk full') { return 'disk-space' }
    if ($text -match '(?i)permission denied|access is denied') { return 'filesystem-permission' }
    if ($text -match '(?i)ResolutionImpossible|conflicting dependencies') { return 'dependency-resolution' }
    if ($text -match '(?i)No matching distribution|Could not find a version') { return 'package-unavailable' }
    if ($text -match '(?i)ReadTimeout|ConnectTimeout|ConnectionError|ProtocolError|Connection reset|SSLError|ProxyError|timed out') { return 'network' }
    if ($text -match '(?i)subprocess-exited-with-error|Failed to build|build backend') { return 'build' }
    return 'unclassified'
}

function Invoke-PipInstall([string]$Python, [string]$BackendPath) {
    $arguments = @(
        '-m', 'pip', 'install', '--disable-pip-version-check', '--timeout', '60',
        '--retries', '5', '--no-input', '-e', $BackendPath
    )
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $output = & $Python @arguments 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($exitCode -ne 0) {
        $category = Get-PipFailureCategory @($output)
        throw "pip install failed with exit code $exitCode (category=$category)."
    }
    return (($output | ForEach-Object { [string]$_ }) -join "`n").Trim()
}

function Ensure-PythonRuntimeDependencies([string]$Python, [scriptblock]$InstallAction = $null) {
    if (Test-PythonRuntimeDependencies $Python) { return $false }
    if ($InstallAction) {
        & $InstallAction | Out-Null
    } else {
        Invoke-PipInstall $Python (Join-Path $Root 'backend') | Out-Null
    }
    return $true
}

function Get-Python($Config) {
    $venvRoot = Join-Path $Root '.venv'
    $python = Join-Path $venvRoot 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        $bootstrap = Resolve-Application $Config.PYTHON_BOOTSTRAP_EXE
        $prefix = @()
        if ([IO.Path]::GetFileName($bootstrap) -ieq 'py.exe') { $prefix = @('-3.12') }
        Invoke-Checked $bootstrap ($prefix + @('-m', 'venv', $venvRoot)) | Out-Null
    }
    $version = Invoke-Checked $python @('-c', "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if ($version -ne '3.12') { throw "Project .venv must use Python 3.12; found $version." }
    Ensure-PythonRuntimeDependencies $python | Out-Null
    return $python
}

function Get-Node($Config) {
    $node = Resolve-Application $Config.NODE_EXE
    $version = Invoke-Checked $node @('-p', 'process.versions.node')
    if (($version -split '\.')[0] -ne '22') { throw "NODE_EXE must be Node.js 22; found $version." }
    $npm = Join-Path (Split-Path $node) 'npm.cmd'
    if (-not (Test-Path -LiteralPath $npm -PathType Leaf)) { $npm = Resolve-Application 'npm.cmd' }
    return @{ File = $node; Npm = $npm }
}

function Get-LocalAlembicHead {
    $revisions = @{}
    Get-ChildItem (Join-Path $Root 'backend\alembic\versions') -Filter '*.py' | ForEach-Object {
        $text = [IO.File]::ReadAllText($_.FullName)
        if ($text -match 'revision:\s*str\s*=\s*["'']([^"'']+)') { $revisions[$matches[1]] = $true }
        if ($text -match 'down_revision[^=]*=\s*["'']([^"'']+)') { $revisions[$matches[1]] = $false }
    }
    $heads = @($revisions.Keys | Where-Object { $revisions[$_] })
    if ($heads.Count -ne 1) { throw 'Expected exactly one local Alembic head.' }
    return $heads[0]
}

function Set-ChildEnvironment($Config, [ValidateSet('Demo', 'Live')] [string]$DataMode) {
    $password = [Uri]::EscapeDataString($Config.REMOTE_DB_PASSWORD)
    $base = "postgresql://$($Config.REMOTE_DB_USER):$password@127.0.0.1:$($Config.LOCAL_DB_PORT)/$($Config.REMOTE_DB_NAME)"
    $env:DATABASE_URL = $base.Replace('postgresql://', 'postgresql+asyncpg://')
    $env:DATABASE_URL_SYNC = $base.Replace('postgresql://', 'postgresql+psycopg://')
    $env:JWT_SECRET = $Config.LOCAL_JWT_SECRET
    $env:PYTHONPATH = Join-Path $Root 'backend\src'
    $env:ENVIRONMENT = 'development'
    $env:WEB_ORIGIN = 'http://localhost:3000'
    $env:NEXT_PUBLIC_API_URL = 'http://localhost:8000/api/v1'
    $env:NEXT_PUBLIC_DATA_BROWSER_V2 = 'true'
    $env:MACROLENS_DATA_MODE = $DataMode.ToLowerInvariant()
}

function ConvertTo-PsycopgConnectionUrl([string]$SqlAlchemyUrl) {
    $driverScheme = 'postgresql+psycopg://'
    if (-not $SqlAlchemyUrl.StartsWith($driverScheme, [StringComparison]::Ordinal)) {
        throw 'Expected a postgresql+psycopg SQLAlchemy URL.'
    }
    return 'postgresql://' + $SqlAlchemyUrl.Substring($driverScheme.Length)
}

function Get-CommandLineHash([string]$CommandLine) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($CommandLine)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    } finally { $sha.Dispose() }
}

function New-ProcessRecord($Process, [string]$RoleName, [string]$Marker) {
    $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$($Process.Id)"
    if (-not $cim -or -not $cim.ExecutablePath -or -not $cim.CommandLine -or $cim.CommandLine.IndexOf($Marker, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
        throw "Could not verify $RoleName process identity."
    }
    return @{
        pid = $Process.Id
        started = $Process.StartTime.ToUniversalTime().Ticks
        role = $RoleName
        executable = [IO.Path]::GetFullPath($cim.ExecutablePath)
        commandLineSha256 = Get-CommandLineHash $cim.CommandLine
    }
}

function Test-ProcessRecord($Record) {
    $process = Get-Process -Id ([int]$Record.pid) -ErrorAction SilentlyContinue
    if (-not $process -or $process.StartTime.ToUniversalTime().Ticks -ne [int64]$Record.started) { return $false }
    $cim = Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$Record.pid)"
    if (-not $cim -or -not $cim.ExecutablePath -or -not $cim.CommandLine) { return $false }
    if (-not [string]::Equals([IO.Path]::GetFullPath($cim.ExecutablePath), [string]$Record.executable, [StringComparison]::OrdinalIgnoreCase)) { return $false }
    return (Get-CommandLineHash $cim.CommandLine) -eq [string]$Record.commandLineSha256
}

function Start-RemoteDevelopment([ValidateSet('Demo', 'Live')] [string]$DataMode) {
    $config = Read-RemoteEnvironment
    $mode = $DataMode.ToLowerInvariant()
    $requiredPorts = @([int]$config.LOCAL_API_PORT)
    if ($mode -eq 'live') { $requiredPorts += [int]$config.LOCAL_DB_PORT }
    $requiredPorts | ForEach-Object { Assert-PortFree $_ }
    Remove-KnownPreviewServer -ValidateOnly
    $python = Get-Python $config
    $node = Get-Node $config
    $postgres = if ($mode -eq 'live') { Get-RemotePostgres $config } else { $null }
    $processes = New-Object Collections.Generic.List[Diagnostics.Process]
    $tunnel = $null
    try {
        $forward = $null
        if ($mode -eq 'live') {
            $ssh = Resolve-Application 'ssh.exe'
            $forward = "127.0.0.1:$($config.LOCAL_DB_PORT):$($postgres.Ip):5432"
            $tunnel = Start-Process -FilePath $ssh -ArgumentList (@('-N', '-T', '-L', $forward) + @(Get-SshArguments $config)) -PassThru -WindowStyle Hidden
            $processes.Add($tunnel)
            Wait-ForPort ([int]$config.LOCAL_DB_PORT) $tunnel
            Set-ChildEnvironment $config $DataMode
            $env:MACROLENS_ALEMBIC_PROBE_URL = ConvertTo-PsycopgConnectionUrl $env:DATABASE_URL_SYNC
            try {
                $query = "import os,psycopg;c=psycopg.connect(os.environ['MACROLENS_ALEMBIC_PROBE_URL']);print(c.execute('select version_num from alembic_version').fetchone()[0]);c.close()"
                $remoteHead = Invoke-Checked $python @('-c', $query)
            } finally {
                Remove-Item Env:MACROLENS_ALEMBIC_PROBE_URL -ErrorAction SilentlyContinue
            }
            $localHead = Get-LocalAlembicHead
            if ($remoteHead -ne $localHead) { throw "Alembic mismatch remote=$remoteHead local=$localHead; migrations were not run." }
        } else {
            Set-ChildEnvironment $config $DataMode
        }
        Remove-KnownPreviewServer
        Assert-PortFree ([int]$config.LOCAL_WEB_PORT)
        $api = Start-Process -FilePath $python -ArgumentList @('-m', 'uvicorn', 'macrolens_api.main:app', '--host', '127.0.0.1', '--port', $config.LOCAL_API_PORT) -WorkingDirectory (Join-Path $Root 'backend') -PassThru -WindowStyle Hidden
        $processes.Add($api)
        Wait-ForPort ([int]$config.LOCAL_API_PORT) $api
        $oldPath = $env:Path
        $env:Path = (Split-Path $node.File) + ';' + $oldPath
        try {
            $npmCli = Join-Path (Split-Path $node.Npm) 'node_modules\npm\bin\npm-cli.js'
            if (Test-Path -LiteralPath $npmCli -PathType Leaf) {
                $web = Start-Process -FilePath $node.File -ArgumentList @($npmCli, '--workspace', 'apps/web', 'run', 'dev', '--', '--port', $config.LOCAL_WEB_PORT) -WorkingDirectory $Root -PassThru -WindowStyle Hidden
            } else {
                $web = Start-Process -FilePath $node.Npm -ArgumentList @('--workspace', 'apps/web', 'run', 'dev', '--', '--port', $config.LOCAL_WEB_PORT) -WorkingDirectory $Root -PassThru -WindowStyle Hidden
            }
        } finally { $env:Path = $oldPath }
        $processes.Add($web)
        Wait-ForPort ([int]$config.LOCAL_WEB_PORT) $web 60
        $records = @()
        if ($mode -eq 'live') { $records += New-ProcessRecord $tunnel 'tunnel' $forward }
        $records += New-ProcessRecord $api 'api' 'macrolens_api.main:app'
        $records += New-ProcessRecord $web 'web' 'apps/web'
        @{ dataMode = $mode; processes = $records } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $State -Encoding UTF8
        $tunnelSummary = if ($mode -eq 'live') { '127.0.0.1:15432' } else { 'disabled' }
        Write-Host "mode=$mode Web http://localhost:3000; API http://localhost:8000/docs; tunnel $tunnelSummary."
    } catch {
        foreach ($process in $processes) {
            if (-not $process.HasExited) { Stop-Process $process.Id -Force -ErrorAction SilentlyContinue }
        }
        throw
    }
}

function Stop-RemoteDevelopment {
    if (-not (Test-Path -LiteralPath $State)) { Write-Host 'STOPPED'; return }
    $saved = Get-Content -LiteralPath $State -Raw | ConvertFrom-Json
    $mismatches = New-Object Collections.Generic.List[string]
    foreach ($record in @($saved.processes) | Sort-Object pid -Descending) {
        if (Test-ProcessRecord $record) {
            & taskkill.exe /PID $record.pid /T /F | Out-Null
            Assert-LastExitCode 'taskkill.exe'
        } elseif (Get-Process -Id ([int]$record.pid) -ErrorAction SilentlyContinue) {
            $mismatches.Add("$($record.role):$($record.pid)")
        }
    }
    if ($mismatches.Count -gt 0) { throw "Process identity mismatch; state retained: $($mismatches -join ', ')." }
    Remove-Item -LiteralPath $State -Force
    Write-Host 'STOPPED'
}

function Show-RemoteDevelopmentStatus {
    if (-not (Test-Path -LiteralPath $State)) { Write-Host 'STOPPED'; return }
    $saved = Get-Content -LiteralPath $State -Raw | ConvertFrom-Json
    $mode = if ($saved.PSObject.Properties['dataMode']) { [string]$saved.dataMode } else { 'live' }
    $statuses = @($saved.processes | ForEach-Object { "$($_.role)=$(Test-ProcessRecord $_)" })
    $tunnelStatus = if ($mode -eq 'demo') { 'disabled' } else { Test-Port 15432 }
    Write-Host "mode=$mode $($statuses -join ' ') tunnel=$tunnelStatus api=$(Test-Port 8000) web=$(Test-Port 3000)"
}

function Deprovision-RemoteDevelopment {
    Stop-RemoteDevelopment
    $config = Read-RemoteEnvironment
    $postgres = Get-RemotePostgres $config
    $revokes = ($Schemas | ForEach-Object {
        "REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA `"$_`" FROM $Role; REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA `"$_`" FROM $Role; REVOKE ALL PRIVILEGES ON SCHEMA `"$_`" FROM $Role;"
    }) -join "`n"
    $sql = @"
BEGIN;
DO `$do`$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_class WHERE relowner = (SELECT oid FROM pg_roles WHERE rolname = '$Role')) THEN
        RAISE EXCEPTION '$Role owns database objects; refusing destructive cleanup';
    END IF;
END `$do`$;
$revokes
REVOKE SELECT ON TABLE public.alembic_version FROM $Role;
REVOKE USAGE ON SCHEMA public FROM $Role;
REVOKE CONNECT ON DATABASE macrolens FROM $Role;
DROP ROLE IF EXISTS $Role;
COMMIT;
"@
    Invoke-RemotePsql $sql $config $postgres
    Remove-Item -LiteralPath $Secret -Force
    Write-Host 'DEPROVISIONED'
}

switch ($Action) {
    Provision { Provision-RemoteDevelopment }
    Start { Start-RemoteDevelopment $DataMode }
    Status { Show-RemoteDevelopmentStatus }
    Stop { Stop-RemoteDevelopment }
    Deprovision { Deprovision-RemoteDevelopment }
}
