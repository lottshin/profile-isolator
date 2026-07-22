# cx-profile.psm1
# Dot-source / Import-Module this so `cx use` mutates the CURRENT shell's CODEX_HOME.

$script:CxToolDir = $PSScriptRoot
$script:CxScript = Join-Path $PSScriptRoot 'cx.ps1'

function cx {
    <#
    .SYNOPSIS
      Codex profile isolation helper (sets CODEX_HOME in current shell for `use`).
    #>
    [CmdletBinding()]
    param(
        [Parameter(Position = 0)]
        [string]$Command = 'help',

        [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
        [string[]]$Rest
    )

    $cmdLower = if ($Command) { $Command.ToLowerInvariant() } else { 'help' }

    # Commands that must run in-process so $env:CODEX_HOME sticks
    $inProcess = @('use', 'set', 'activate')

    # Shorthand profile name: `cx Official`
    $root = if ($env:CODEX_PROFILES_ROOT) { $env:CODEX_PROFILES_ROOT } else { Join-Path $env:USERPROFILE 'CodexProfiles' }
    $maybeProfile = Join-Path $root $Command
    $isShorthandUse = $false
    if ($Command -and (Test-Path -LiteralPath $maybeProfile -PathType Container) -and $cmdLower -notin @(
            'help', 'init', 'list', 'ls', 'new', 'create', 'add', 'import', 'cp', 'copy',
            'remove', 'rm', 'delete', 'show', 'info', 'path', 'which', 'current',
            'use', 'set', 'activate', 'run', 'exec', 'start', 'open', 'window',
            'edit', 'doctor', 'check', '-h', '--help'
        )) {
        $isShorthandUse = $true
        $Rest = @($Command) + @($Rest)
        $Command = 'use'
        $cmdLower = 'use'
    }

    if ($cmdLower -in $inProcess -or $isShorthandUse) {
        # Parse profile name
        $name = $null
        if ($Rest -and $Rest.Count -ge 1) { $name = $Rest[0] }
        elseif ($isShorthandUse) { $name = $Command }

        if (-not $name) {
            Write-Host "Usage: cx use <name>" -ForegroundColor Yellow
            return
        }

        $profilePath = Join-Path $root $name
        if (-not (Test-Path -LiteralPath $profilePath -PathType Container)) {
            Write-Host "Error: profile '$name' not found at $profilePath" -ForegroundColor Red
            return
        }

        # Doctor lite (cwd trap)
        $cwd = (Get-Location).Path
        if ([IO.Path]::GetFullPath($cwd).TrimEnd('\') -ieq [IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\')) {
            Write-Host "[doctor] CWD is your user profile. ~/.codex may override this profile. cd into a project first." -ForegroundColor Red
        }

        $env:CODEX_HOME = (Resolve-Path -LiteralPath $profilePath).Path
        Write-Host "CODEX_HOME => $env:CODEX_HOME" -ForegroundColor Green

        $cfg = Join-Path $env:CODEX_HOME 'config.toml'
        if (Test-Path -LiteralPath $cfg) {
            $text = Get-Content -LiteralPath $cfg -Raw
            if ($text -match '(?m)^\s*model\s*=\s*"([^"]+)"') {
                Write-Host "model      => $($Matches[1])" -ForegroundColor DarkGray
            }
            if ($text -match '(?m)^\s*model_provider\s*=\s*"([^"]+)"') {
                Write-Host "provider   => $($Matches[1])" -ForegroundColor DarkGray
            }
        }
        return
    }

    # Everything else: delegate to cx.ps1
    $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $script:CxScript, $Command)
    if ($Rest) { $argList += $Rest }
    & powershell.exe @argList
    # Do not return LASTEXITCODE — it would print "0" in interactive use.
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        $global:LASTEXITCODE = $LASTEXITCODE
    }
}

function Set-CxProfile {
    param([Parameter(Mandatory)][string]$Name)
    cx use $Name
}

function Start-CxProfile {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$CodexArgs
    )
    if ($CodexArgs) {
        cx run $Name @CodexArgs
    } else {
        cx run $Name
    }
}

Export-ModuleMember -Function cx, Set-CxProfile, Start-CxProfile
