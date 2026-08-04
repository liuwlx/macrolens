Describe 'remote-dev PowerShell contract' {
    It 'passes static and local process-safety checks without remote access' {
        $testScript = Join-Path $PSScriptRoot 'remote-dev-static.ps1'
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $testScript
        $LASTEXITCODE | Should Be 0
    }
}
