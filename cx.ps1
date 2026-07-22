#Requires -Version 5.1
<#
.SYNOPSIS
  Codex CLI profile isolation tool (CODEX_HOME multi-profile manager).

.DESCRIPTION
  Manage isolated Codex CLI configs so each terminal can use a different
  provider / model / API key without affecting other sessions.

  Profiles live under CODEX_PROFILES_ROOT (default: %USERPROFILE%\CodexProfiles).
  Each profile is a directory with config.toml + auth.json.

.EXAMPLE
  cx init
  cx new Official -FromCurrent
  cx new OpenRouter
  cx list
  cx use Official
  cx run OpenRouter
  cx import Official -FromCurrent
  cx doctor Official
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command = 'help',

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

function Get-CxRoot {
    if ($env:CODEX_PROFILES_ROOT -and $env:CODEX_PROFILES_ROOT.Trim()) {
        return [System.IO.Path]::GetFullPath($env:CODEX_PROFILES_ROOT.Trim())
    }
    return (Join-Path $env:USERPROFILE 'CodexProfiles')
}

function Get-DefaultCodexHome {
    if ($env:CODEX_HOME -and (Test-Path $env:CODEX_HOME)) {
        # When already inside a profile session, still treat ~/.codex as the "source of truth"
        # for -FromCurrent imports only if user explicitly points there.
    }
    return (Join-Path $env:USERPROFILE '.codex')
}

function Get-ProfilePath {
    param([Parameter(Mandatory)][string]$Name)
    $safe = Get-SafeProfileName $Name
    return (Join-Path (Get-CxRoot) $safe)
}

function Get-SafeProfileName {
    param([Parameter(Mandatory)][string]$Name)
    $n = $Name.Trim()
    if (-not $n) { throw 'Profile name is empty.' }
    if ($n -match '[\\/:*?"<>|]') {
        throw "Invalid profile name '$n'. Avoid: \ / : * ? `" < > |"
    }
    if ($n -in @('.', '..')) { throw "Invalid profile name '$n'." }
    return $n
}

function Assert-ProfileExists {
    param([Parameter(Mandatory)][string]$Name)
    $path = Get-ProfilePath $Name
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Profile '$Name' not found at $path`nRun: cx list"
    }
    return $path
}

function Test-IsUnderPath {
    param(
        [Parameter(Mandatory)][string]$Child,
        [Parameter(Mandatory)][string]$Parent
    )
    $c = [System.IO.Path]::GetFullPath($Child).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    $p = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    return $c.StartsWith($p, [System.StringComparison]::OrdinalIgnoreCase)
}

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

function Get-ConfigSummary {
    param([string]$ProfileDir)
    $cfg = Join-Path $ProfileDir 'config.toml'
    $auth = Join-Path $ProfileDir 'auth.json'
    $model = $null
    $provider = $null
    $baseUrl = $null
    $hasAuth = Test-Path -LiteralPath $auth
    $hasCfg = Test-Path -LiteralPath $cfg

    if ($hasCfg) {
        $text = Get-Content -LiteralPath $cfg -Raw -ErrorAction SilentlyContinue
        if ($text) {
            if ($text -match '(?m)^\s*model\s*=\s*"([^"]+)"') { $model = $Matches[1] }
            if ($text -match '(?m)^\s*model_provider\s*=\s*"([^"]+)"') { $provider = $Matches[1] }
            if ($text -match '(?m)^\s*base_url\s*=\s*"([^"]+)"') { $baseUrl = $Matches[1] }
        }
    }

    [pscustomobject]@{
        HasConfig = $hasCfg
        HasAuth   = $hasAuth
        Model     = $model
        Provider  = $provider
        BaseUrl   = $baseUrl
    }
}

function Sanitize-CodexConfigText {
    <#
      Strip CC Switch model catalog line that breaks isolated homes:
        model_catalog_json = "cc-switch-model-catalog.json"
    #>
    param([string]$Text)
    if (-not $Text) { return $Text }
    $lines = $Text -split "`r?`n"
    $kept = foreach ($line in $lines) {
        if ($line -match '^\s*model_catalog_json\s*=') {
            Write-Host "  [sanitize] removed: $($line.Trim())" -ForegroundColor Yellow
            continue
        }
        $line
    }
    return ($kept -join "`n")
}

function Copy-CodexProfileFiles {
    param(
        [Parameter(Mandatory)][string]$SourceDir,
        [Parameter(Mandatory)][string]$DestDir,
        [switch]$Force
    )
    if (-not (Test-Path -LiteralPath $SourceDir -PathType Container)) {
        throw "Source directory not found: $SourceDir"
    }
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

    $cfgSrc = Join-Path $SourceDir 'config.toml'
    $authSrc = Join-Path $SourceDir 'auth.json'
    $cfgDst = Join-Path $DestDir 'config.toml'
    $authDst = Join-Path $DestDir 'auth.json'

    if ((Test-Path -LiteralPath $cfgDst) -and -not $Force) {
        throw "config.toml already exists in $DestDir (use -Force to overwrite)"
    }
    if ((Test-Path -LiteralPath $authDst) -and -not $Force) {
        throw "auth.json already exists in $DestDir (use -Force to overwrite)"
    }

    if (Test-Path -LiteralPath $cfgSrc) {
        $raw = Get-Content -LiteralPath $cfgSrc -Raw
        $clean = Sanitize-CodexConfigText $raw
        # UTF-8 without BOM for TOML friendliness
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($cfgDst, $clean, $utf8)
        Write-Host "  wrote config.toml" -ForegroundColor Green
    } else {
        Write-Host "  skip config.toml (source missing)" -ForegroundColor Yellow
    }

    if (Test-Path -LiteralPath $authSrc) {
        Copy-Item -LiteralPath $authSrc -Destination $authDst -Force
        Write-Host "  wrote auth.json" -ForegroundColor Green
    } else {
        Write-Host "  skip auth.json (source missing)" -ForegroundColor Yellow
    }
}

function Write-StubConfig {
    param([Parameter(Mandatory)][string]$DestDir)
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    $cfg = Join-Path $DestDir 'config.toml'
    $auth = Join-Path $DestDir 'auth.json'

    if (-not (Test-Path -LiteralPath $cfg)) {
        $stub = @'
# Codex profile config — edit me
# model_provider = "custom"
# model = "gpt-5.5"
# model_reasoning_effort = "high"
#
# [model_providers.custom]
# name = "MyProvider"
# wire_api = "responses"
# base_url = "https://api.example.com/v1"
# requires_openai_auth = true
'@
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($cfg, $stub.TrimStart() + "`n", $utf8)
    }
    if (-not (Test-Path -LiteralPath $auth)) {
        $authStub = @'
{
  "OPENAI_API_KEY": "sk-REPLACE_ME"
}
'@
        $utf8 = New-Object System.Text.UTF8Encoding $false
        [System.IO.File]::WriteAllText($auth, $authStub.TrimStart() + "`n", $utf8)
    }
}

function Get-CwdProjectCodexConflict {
    <#
      Pitfall from the tutorial: if cwd is ~ and ~/.codex/config.toml exists,
      Codex may load it as project-local config and override CODEX_HOME settings.
    #>
    $cwd = (Get-Location).Path
    $projectCfg = Join-Path $cwd '.codex\config.toml'
    $homeCodex = Join-Path $env:USERPROFILE '.codex'
    $result = @()

    if (Test-Path -LiteralPath $projectCfg) {
        $result += [pscustomobject]@{
            Level   = 'warn'
            Message = "CWD has project config: $projectCfg (may override profile model / settings)"
        }
    }

    # Classic trap: cwd is user home, so ~/.codex becomes "<cwd>\.codex"
    $cwdCodex = Join-Path $cwd '.codex'
    if ((Test-Path -LiteralPath $cwdCodex) -and (Test-IsUnderPath -Child $cwdCodex -Parent $env:USERPROFILE)) {
        if ([System.IO.Path]::GetFullPath($cwd).TrimEnd('\') -ieq [System.IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\')) {
            $result += [pscustomobject]@{
                Level   = 'error'
                Message = "CWD is your user profile ($cwd). Default ~/.codex will be treated as project-local config and can override CODEX_HOME. cd into a project first."
            }
        }
    }

    # Profiles nested under default .codex
    $root = Get-CxRoot
    if (Test-IsUnderPath -Child $root -Parent $homeCodex) {
        $result += [pscustomobject]@{
            Level   = 'warn'
            Message = "Profiles root is under default .codex ($root). Prefer a path outside ~/.codex (e.g. %USERPROFILE%\CodexProfiles)."
        }
    }

    # Always return a flat Object[] (possibly empty) without unary-comma wrapping
    return @($result)
}

function Resolve-LaunchWorkingDirectory {
    param([string]$WorkDir)
    if ($WorkDir) {
        if (-not (Test-Path -LiteralPath $WorkDir -PathType Container)) {
            throw "Working directory not found: $WorkDir"
        }
        return (Resolve-Path -LiteralPath $WorkDir).Path
    }

    $cwd = (Get-Location).Path
    $issues = @(Get-CwdProjectCodexConflict | Where-Object { $_ -and $_.PSObject.Properties['Level'] })
    $hard = @($issues | Where-Object { $_.Level -eq 'error' })
    if ($hard.Count -gt 0) {
        foreach ($i in $hard) { Write-Host "[doctor] $($i.Message)" -ForegroundColor Red }
        # Fall back to a neutral temp-like location: profile root parent or Desktop
        $fallback = Join-Path $env:USERPROFILE 'Desktop'
        if (-not (Test-Path $fallback)) { $fallback = $env:TEMP }
        Write-Host "[cx] CWD unsafe for CODEX_HOME isolation; launching with -WorkDir $fallback" -ForegroundColor Yellow
        Write-Host "[cx] Tip: cd into your project, or pass -WorkDir <project>" -ForegroundColor Yellow
        return $fallback
    }
    foreach ($i in $issues) {
        $color = if ($i.Level -eq 'warn') { 'Yellow' } else { 'Red' }
        Write-Host "[doctor] $($i.Message)" -ForegroundColor $color
    }
    return $cwd
}

function Find-CodexCommand {
    $cmd = Get-Command codex -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidates = @(
        (Join-Path $env:APPDATA 'npm\codex.ps1'),
        (Join-Path $env:APPDATA 'npm\codex.cmd'),
        'F:\nodejs\codex.ps1'
    )
    foreach ($c in $candidates) {
        if (Test-Path -LiteralPath $c) { return $c }
    }
    return $null
}

# ---------------------------------------------------------------------------
# Argument parsing helpers
# ---------------------------------------------------------------------------

function ConvertTo-ArgMap {
    param([string[]]$Tokens)
    if ($null -eq $Tokens) { $Tokens = @() }
    $pos = New-Object System.Collections.Generic.List[string]
    $flags = @{}
    $i = 0
    $tokenArr = @($Tokens | Where-Object { $null -ne $_ })
    while ($i -lt $tokenArr.Count) {
        $t = $tokenArr[$i]
        if ($t -match '^--([^=]+)=(.*)$') {
            $flags[$Matches[1]] = $Matches[2]
        } elseif ($t -match '^--(.+)$') {
            $key = $Matches[1]
            $next = if ($i + 1 -lt $tokenArr.Count) { $tokenArr[$i + 1] } else { $null }
            if ($null -ne $next -and $next -notmatch '^-') {
                $flags[$key] = $next
                $i++
            } else {
                $flags[$key] = $true
            }
        } elseif ($t -match '^-([A-Za-z]+)$') {
            # PowerShell-style: -FromCurrent, -Force, -WorkDir path
            $key = $Matches[1]
            $next = if ($i + 1 -lt $tokenArr.Count) { $tokenArr[$i + 1] } else { $null }
            if ($null -ne $next -and $next -notmatch '^-') {
                # Heuristic: known switch-only flags
                $switchOnly = @('FromCurrent', 'Force', 'Help', 'h', 'All', 'Json', 'DryRun', 'Yes')
                if ($key -in $switchOnly) {
                    $flags[$key] = $true
                } else {
                    $flags[$key] = $next
                    $i++
                }
            } else {
                $flags[$key] = $true
            }
        } else {
            [void]$pos.Add([string]$t)
        }
        $i++
    }
    return [pscustomobject]@{ Positional = @($pos.ToArray()); Flags = $flags }
}

function Test-Flag {
    param($Flags, [string[]]$Names)
    foreach ($n in $Names) {
        if ($Flags.ContainsKey($n)) {
            $v = $Flags[$n]
            if ($v -is [bool]) { return [bool]$v }
            if ("$v" -eq 'true' -or "$v" -eq '1') { return $true }
            if ("$v" -eq 'false' -or "$v" -eq '0') { return $false }
            return $true
        }
    }
    return $false
}

function Get-FlagValue {
    param($Flags, [string[]]$Names, $Default = $null)
    foreach ($n in $Names) {
        if ($Flags.ContainsKey($n)) {
            $v = $Flags[$n]
            if ($v -is [bool]) { return $Default }
            return $v
        }
    }
    return $Default
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

function Invoke-CxHelp {
    $root = Get-CxRoot
    @"

  cx - Codex CLI profile isolation (CODEX_HOME manager)

  Profiles root : $root
  Override root : set CODEX_PROFILES_ROOT

  Setup
    cx init                         Create profiles root
    cx new <name> [-FromCurrent]    Create profile (optionally copy ~/.codex)
    cx import <name> -FromCurrent   Import config.toml + auth.json from ~/.codex
    cx import <name> -Source <dir>  Import from another directory
    cx remove <name> [-Yes]         Delete a profile

  Use
    cx list                         List profiles
    cx show <name>                  Show profile summary
    cx use <name>                   Set CODEX_HOME in CURRENT shell (dot-source)
    cx run <name> [-- <codex args>] Run codex under profile (subprocess)
    cx open <name>                  Open a new PowerShell window with profile
    cx which                        Print current CODEX_HOME
    cx path <name>                  Print profile directory
    cx edit <name>                  Open config.toml in default editor
    cx doctor [name]                Check isolation pitfalls

  Examples
    cx init
    cx new Official -FromCurrent
    cx new OpenRouter
    cx edit OpenRouter
    cx use Official
    codex
    cx run OpenRouter
    cx run OpenRouter -- resume
    cx open Official

  Notes
    - 'cx use' only affects the current shell if you install the module
      (see install.ps1) or dot-source the function.
    - Do NOT put profiles under %USERPROFILE%\.codex
    - Avoid launching while CWD is your user home directory
    - CC Switch 'model_catalog_json' lines are stripped on import

"@ | Write-Host
}

function Invoke-CxInit {
    $root = Get-CxRoot
    if (-not (Test-Path -LiteralPath $root)) {
        New-Item -ItemType Directory -Force -Path $root | Out-Null
        Write-Host "Created profiles root: $root" -ForegroundColor Green
    } else {
        Write-Host "Profiles root already exists: $root" -ForegroundColor DarkGray
    }

    $readme = Join-Path $root 'README.txt'
    if (-not (Test-Path -LiteralPath $readme)) {
        @(
            'CodexProfiles — each subfolder is an isolated CODEX_HOME'
            ''
            'Minimal files per profile:'
            '  config.toml'
            '  auth.json'
            ''
            'Launch:'
            '  $env:CODEX_HOME = "HERE\ProfileName"'
            '  codex'
            ''
            'Or use the cx tool:'
            '  cx use ProfileName'
            '  cx run ProfileName'
        ) -join "`r`n" | Set-Content -LiteralPath $readme -Encoding UTF8
    }

    $homeCodex = Join-Path $env:USERPROFILE '.codex'
    if (Test-IsUnderPath -Child $root -Parent $homeCodex) {
        Write-Host "WARNING: root is under ~/.codex — this can cause project-local config conflicts." -ForegroundColor Yellow
        Write-Host "Set a safer root, e.g.:" -ForegroundColor Yellow
        Write-Host '  $env:CODEX_PROFILES_ROOT = "$env:USERPROFILE\CodexProfiles"' -ForegroundColor Yellow
    } else {
        Write-Host "OK: root is outside default ~/.codex" -ForegroundColor Green
    }
}

function Invoke-CxList {
    param($ArgsObj)
    $root = Get-CxRoot
    if (-not (Test-Path -LiteralPath $root)) {
        Write-Host "No profiles root yet. Run: cx init" -ForegroundColor Yellow
        return
    }

    $dirs = Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch '^\.' } |
        Sort-Object Name

    if (-not $dirs) {
        Write-Host "No profiles in $root" -ForegroundColor Yellow
        Write-Host "Create one: cx new Official -FromCurrent"
        return
    }

    $current = $env:CODEX_HOME
    $rows = foreach ($d in $dirs) {
        $s = Get-ConfigSummary $d.FullName
        $mark = if ($current -and ([IO.Path]::GetFullPath($current).TrimEnd('\') -ieq $d.FullName.TrimEnd('\'))) { '*' } else { ' ' }
        [pscustomobject]@{
            Current  = $mark
            Name     = $d.Name
            Model    = $(if ($s.Model) { $s.Model } else { '-' })
            Provider = $(if ($s.Provider) { $s.Provider } else { '-' })
            BaseUrl  = $(if ($s.BaseUrl) { $s.BaseUrl } else { '-' })
            Auth     = $(if ($s.HasAuth) { 'yes' } else { 'no' })
            Config   = $(if ($s.HasConfig) { 'yes' } else { 'no' })
        }
    }

    if (Test-Flag $ArgsObj.Flags @('Json')) {
        $rows | ConvertTo-Json -Depth 4
    } else {
        Write-Host "Profiles root: $root" -ForegroundColor DarkGray
        if ($current) {
            Write-Host "CODEX_HOME   : $current" -ForegroundColor DarkGray
        } else {
            Write-Host "CODEX_HOME   : (default ~/.codex)" -ForegroundColor DarkGray
        }
        Write-Host ""
        $rows | Format-Table -AutoSize Current, Name, Model, Provider, Auth, Config, BaseUrl | Out-String | Write-Host
        Write-Host "* = active CODEX_HOME in this shell" -ForegroundColor DarkGray
    }
}

function Invoke-CxNew {
    param($ArgsObj)
    if ($ArgsObj.Positional.Count -lt 1) { throw 'Usage: cx new <name> [-FromCurrent] [-Force]' }
    $name = Get-SafeProfileName $ArgsObj.Positional[0]
    $path = Get-ProfilePath $name
    $fromCurrent = Test-Flag $ArgsObj.Flags @('FromCurrent', 'from-current')
    $force = Test-Flag $ArgsObj.Flags @('Force', 'force')

    if ((Test-Path -LiteralPath $path) -and -not $force) {
        throw "Profile already exists: $path (use -Force)"
    }

    $root = Get-CxRoot
    if (-not (Test-Path -LiteralPath $root)) {
        New-Item -ItemType Directory -Force -Path $root | Out-Null
    }

    Write-Host "Creating profile '$name' -> $path" -ForegroundColor Cyan
    if ($fromCurrent) {
        $src = Get-DefaultCodexHome
        Write-Host "Importing from $src" -ForegroundColor DarkGray
        Copy-CodexProfileFiles -SourceDir $src -DestDir $path -Force:$force
    } else {
        Write-StubConfig -DestDir $path
        Write-Host "  wrote stub config.toml + auth.json" -ForegroundColor Green
        Write-Host "  edit with: cx edit $name" -ForegroundColor DarkGray
    }
    Write-Host "Done. Launch: cx use $name   or   cx run $name" -ForegroundColor Green
}

function Invoke-CxImport {
    param($ArgsObj)
    if ($ArgsObj.Positional.Count -lt 1) { throw 'Usage: cx import <name> -FromCurrent | -Source <dir> [-Force]' }
    $name = Get-SafeProfileName $ArgsObj.Positional[0]
    $path = Get-ProfilePath $name
    $force = Test-Flag $ArgsObj.Flags @('Force', 'force')
    $fromCurrent = Test-Flag $ArgsObj.Flags @('FromCurrent', 'from-current')
    $source = Get-FlagValue $ArgsObj.Flags @('Source', 'source', 'From', 'from')

    if ($fromCurrent) {
        $source = Get-DefaultCodexHome
    }
    if (-not $source) { throw 'Specify -FromCurrent or -Source <dir>' }

    Write-Host "Importing into profile '$name'" -ForegroundColor Cyan
    Write-Host "  from: $source" -ForegroundColor DarkGray
    Write-Host "  to  : $path" -ForegroundColor DarkGray
    Copy-CodexProfileFiles -SourceDir $source -DestDir $path -Force:$force
    Write-Host "Done." -ForegroundColor Green
}

function Invoke-CxRemove {
    param($ArgsObj)
    if ($ArgsObj.Positional.Count -lt 1) { throw 'Usage: cx remove <name> [-Yes]' }
    $name = Get-SafeProfileName $ArgsObj.Positional[0]
    $path = Assert-ProfileExists $name
    $yes = Test-Flag $ArgsObj.Flags @('Yes', 'yes', 'Force', 'force')

    if (-not $yes) {
        Write-Host "About to delete: $path" -ForegroundColor Yellow
        Write-Host "Re-run with -Yes to confirm." -ForegroundColor Yellow
        return
    }
    Remove-Item -LiteralPath $path -Recurse -Force
    Write-Host "Removed profile '$name'" -ForegroundColor Green
}

function Invoke-CxShow {
    param($ArgsObj)
    if ($ArgsObj.Positional.Count -lt 1) { throw 'Usage: cx show <name>' }
    $name = Get-SafeProfileName $ArgsObj.Positional[0]
    $path = Assert-ProfileExists $name
    $s = Get-ConfigSummary $path

    Write-Host "Profile : $name" -ForegroundColor Cyan
    Write-Host "Path    : $path"
    Write-Host "Model   : $(if ($s.Model) { $s.Model } else { '(not set)' })"
    Write-Host "Provider: $(if ($s.Provider) { $s.Provider } else { '(not set)' })"
    Write-Host "Base URL: $(if ($s.BaseUrl) { $s.BaseUrl } else { '(not set)' })"
    Write-Host "config  : $(if ($s.HasConfig) { 'yes' } else { 'MISSING' })"
    Write-Host "auth    : $(if ($s.HasAuth) { 'yes' } else { 'MISSING' })"
    Write-Host ""
    Write-Host "Shell:" -ForegroundColor DarkGray
    Write-Host "  `$env:CODEX_HOME = '$path'"
    Write-Host "  codex"
}

function Invoke-CxPath {
    param($ArgsObj)
    if ($ArgsObj.Positional.Count -lt 1) {
        Write-Output (Get-CxRoot)
        return
    }
    $name = Get-SafeProfileName $ArgsObj.Positional[0]
    Write-Output (Assert-ProfileExists $name)
}

function Invoke-CxWhich {
    if ($env:CODEX_HOME) {
        Write-Host "CODEX_HOME = $env:CODEX_HOME" -ForegroundColor Green
        if (Test-Path -LiteralPath $env:CODEX_HOME) {
            $s = Get-ConfigSummary $env:CODEX_HOME
            Write-Host "model      = $(if ($s.Model) { $s.Model } else { '-' })"
            Write-Host "provider   = $(if ($s.Provider) { $s.Provider } else { '-' })"
        }
    } else {
        $def = Get-DefaultCodexHome
        Write-Host "CODEX_HOME not set (using default $def)" -ForegroundColor Yellow
    }
}

function Invoke-CxUse {
    param($ArgsObj)
    if ($ArgsObj.Positional.Count -lt 1) { throw 'Usage: cx use <name>   (prefer: . cx use <name>  or installed function)' }
    $name = Get-SafeProfileName $ArgsObj.Positional[0]
    $path = Assert-ProfileExists $name

    $issues = @(Get-CwdProjectCodexConflict | Where-Object { $_ -and $_.PSObject.Properties['Level'] })
    foreach ($i in $issues) {
        $color = if ($i.Level -eq 'error') { 'Red' } else { 'Yellow' }
        Write-Host "[doctor] $($i.Message)" -ForegroundColor $color
    }

    $env:CODEX_HOME = $path
    Write-Host "CODEX_HOME => $path" -ForegroundColor Green
    $s = Get-ConfigSummary $path
    if ($s.Model) { Write-Host "model      => $($s.Model)" -ForegroundColor DarkGray }
    if ($s.Provider) { Write-Host "provider   => $($s.Provider)" -ForegroundColor DarkGray }

    # Detect whether env assignment will stick (dot-sourced vs subprocess)
    if ($MyInvocation.PSCommandPath -and -not $cxDotSourced) {
        # When run as script file in child scope, parent shell won't see $env changes
        # unless the user uses the function wrapper. Hint either way is useful.
    }

    # Emit a marker line scripts/hooks can parse
    Write-Output "CODEX_HOME=$path"
}

function Invoke-CxRun {
    param($ArgsObj)
    if ($ArgsObj.Positional.Count -lt 1) { throw 'Usage: cx run <name> [-- <codex args>]' }

    $name = Get-SafeProfileName $ArgsObj.Positional[0]
    $path = Assert-ProfileExists $name
    $workDir = Get-FlagValue $ArgsObj.Flags @('WorkDir', 'workdir', 'Cwd', 'cwd')
    $wd = Resolve-LaunchWorkingDirectory -WorkDir $workDir

    # Remaining positional after name = codex args; also allow -- separator already stripped by caller
    $codexArgs = @()
    if ($ArgsObj.Positional.Count -gt 1) {
        $codexArgs = $ArgsObj.Positional[1..($ArgsObj.Positional.Count - 1)]
    }

    $codex = Find-CodexCommand
    if (-not $codex) { throw 'codex command not found in PATH' }

    Write-Host "Profile : $name" -ForegroundColor Cyan
    Write-Host "HOME    : $path" -ForegroundColor DarkGray
    Write-Host "CWD     : $wd" -ForegroundColor DarkGray
    Write-Host "Command : codex $($codexArgs -join ' ')" -ForegroundColor DarkGray

    $prevHome = $env:CODEX_HOME
    $prevLoc = (Get-Location).Path
    try {
        $env:CODEX_HOME = $path
        Set-Location -LiteralPath $wd
        if ($codexArgs.Count -gt 0) {
            & $codex @codexArgs
        } else {
            & $codex
        }
        return $LASTEXITCODE
    } finally {
        if ($null -eq $prevHome) {
            Remove-Item Env:CODEX_HOME -ErrorAction SilentlyContinue
        } else {
            $env:CODEX_HOME = $prevHome
        }
        Set-Location -LiteralPath $prevLoc
    }
}

function Invoke-CxOpen {
    param($ArgsObj)
    if ($ArgsObj.Positional.Count -lt 1) { throw 'Usage: cx open <name> [-WorkDir <path>]' }
    $name = Get-SafeProfileName $ArgsObj.Positional[0]
    $path = Assert-ProfileExists $name
    $workDir = Get-FlagValue $ArgsObj.Flags @('WorkDir', 'workdir', 'Cwd', 'cwd')
    if (-not $workDir) {
        $workDir = Resolve-LaunchWorkingDirectory
    } else {
        $workDir = (Resolve-Path -LiteralPath $workDir).Path
    }

    # New window keeps CODEX_HOME for the whole session
    $psCmd = @"
`$env:CODEX_HOME = '$($path.Replace("'","''"))'
Set-Location -LiteralPath '$($workDir.Replace("'","''"))'
Write-Host ('[cx] CODEX_HOME=' + `$env:CODEX_HOME) -ForegroundColor Green
Write-Host ('[cx] profile   = $name') -ForegroundColor DarkGray
Write-Host 'Type: codex' -ForegroundColor DarkGray
"@

    Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoExit',
        '-NoLogo',
        '-Command', $psCmd
    ) | Out-Null

    Write-Host "Opened new PowerShell with profile '$name'" -ForegroundColor Green
    Write-Host "  CODEX_HOME=$path" -ForegroundColor DarkGray
    Write-Host "  CWD       =$workDir" -ForegroundColor DarkGray
}

function Invoke-CxEdit {
    param($ArgsObj)
    if ($ArgsObj.Positional.Count -lt 1) { throw 'Usage: cx edit <name> [config|auth]' }
    $name = Get-SafeProfileName $ArgsObj.Positional[0]
    $path = Assert-ProfileExists $name
    $which = if ($ArgsObj.Positional.Count -gt 1) { $ArgsObj.Positional[1] } else { 'config' }

    $file = switch -Regex ($which) {
        '^(config|toml|cfg)$' { Join-Path $path 'config.toml' }
        '^(auth|key|json)$' { Join-Path $path 'auth.json' }
        default { throw "Unknown target '$which' (use config|auth)" }
    }
    if (-not (Test-Path -LiteralPath $file)) {
        throw "File not found: $file"
    }

    if (Get-Command code -ErrorAction SilentlyContinue) {
        & code -- $file
    } elseif (Get-Command cursor -ErrorAction SilentlyContinue) {
        & cursor -- $file
    } else {
        Invoke-Item -LiteralPath $file
    }
    Write-Host "Opened $file" -ForegroundColor Green
}

function Invoke-CxDoctor {
    param($ArgsObj)
    $root = Get-CxRoot
    Write-Host "=== cx doctor ===" -ForegroundColor Cyan
    Write-Host "Profiles root : $root"
    Write-Host "Default codex : $(Get-DefaultCodexHome)"
    Write-Host "CODEX_HOME    : $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { '(unset)' })"
    Write-Host "CWD           : $((Get-Location).Path)"
    Write-Host ""

    $codex = Find-CodexCommand
    if ($codex) {
        Write-Host "[ok] codex found: $codex" -ForegroundColor Green
    } else {
        Write-Host "[!!] codex not found in PATH" -ForegroundColor Red
    }

    if (Test-Path -LiteralPath $root) {
        Write-Host "[ok] profiles root exists" -ForegroundColor Green
    } else {
        Write-Host "[!!] profiles root missing — run: cx init" -ForegroundColor Red
    }

    $homeCodex = Join-Path $env:USERPROFILE '.codex'
    if (Test-IsUnderPath -Child $root -Parent $homeCodex) {
        Write-Host "[!!] profiles root is under ~/.codex — high risk of project-local override" -ForegroundColor Red
    } else {
        Write-Host "[ok] profiles root outside ~/.codex" -ForegroundColor Green
    }

    $issues = @(Get-CwdProjectCodexConflict | Where-Object { $_ -and $_.PSObject.Properties['Level'] })
    if ($issues.Count -eq 0) {
        Write-Host "[ok] CWD looks safe for isolation" -ForegroundColor Green
    } else {
        foreach ($i in $issues) {
            $color = if ($i.Level -eq 'error') { 'Red' } else { 'Yellow' }
            Write-Host "[$($i.Level)] $($i.Message)" -ForegroundColor $color
        }
    }

    if ($ArgsObj.Positional.Count -ge 1) {
        $name = Get-SafeProfileName $ArgsObj.Positional[0]
        $path = Assert-ProfileExists $name
        Write-Host ""
        Write-Host "--- profile: $name ---" -ForegroundColor Cyan
        $s = Get-ConfigSummary $path
        if (-not $s.HasConfig) { Write-Host "[!!] missing config.toml" -ForegroundColor Red } else { Write-Host "[ok] config.toml" -ForegroundColor Green }
        if (-not $s.HasAuth) { Write-Host "[!!] missing auth.json" -ForegroundColor Red } else { Write-Host "[ok] auth.json" -ForegroundColor Green }

        $cfg = Join-Path $path 'config.toml'
        if (Test-Path -LiteralPath $cfg) {
            $text = Get-Content -LiteralPath $cfg -Raw
            if ($text -match 'model_catalog_json') {
                Write-Host "[!!] config contains model_catalog_json (CC Switch) — remove it or re-import with cx import -Force" -ForegroundColor Red
            } else {
                Write-Host "[ok] no model_catalog_json" -ForegroundColor Green
            }
            if ($s.Model) { Write-Host "[ok] model = $($s.Model)" -ForegroundColor Green }
            if ($s.BaseUrl) { Write-Host "[ok] base_url = $($s.BaseUrl)" -ForegroundColor Green }
        }
    } else {
        Write-Host ""
        Write-Host "Tip: cx doctor <name> for per-profile checks" -ForegroundColor DarkGray
    }
}

# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

# Support: cx help / cx -h / cx --help
if ($Command -in @('-h', '--help', '/?')) { $Command = 'help' }

# Allow "cx run Name -- resume foo" style: Rest may contain '--'
# Important: @($null) is a 1-element array in PowerShell — normalize first.
$restTokens = if ($null -eq $Rest) { @() } else { @($Rest | Where-Object { $null -ne $_ }) }
$restList = New-Object System.Collections.Generic.List[string]
$sawSep = $false
$afterSep = New-Object System.Collections.Generic.List[string]
foreach ($t in $restTokens) {
    if (-not $sawSep -and $t -eq '--') { $sawSep = $true; continue }
    if ($sawSep) { [void]$afterSep.Add([string]$t) } else { [void]$restList.Add([string]$t) }
}
$parsed = ConvertTo-ArgMap -Tokens $restList.ToArray()
if ($afterSep.Count -gt 0) {
    # append post -- tokens as positionals (codex args)
    $parsed = [pscustomobject]@{
        Positional = @($parsed.Positional + $afterSep.ToArray())
        Flags      = $parsed.Flags
    }
}
# Normalize empty positionals (avoid Count quirks on scalar)
if ($null -eq $parsed.Positional) {
    $parsed = [pscustomobject]@{ Positional = @(); Flags = $parsed.Flags }
} elseif ($parsed.Positional -isnot [array]) {
    $parsed = [pscustomobject]@{ Positional = @($parsed.Positional); Flags = $parsed.Flags }
}

try {
    switch -Regex ($Command.ToLowerInvariant()) {
        '^(help)$' { Invoke-CxHelp }
        '^(init)$' { Invoke-CxInit }
        '^(list|ls)$' { Invoke-CxList -ArgsObj $parsed }
        '^(new|create|add)$' { Invoke-CxNew -ArgsObj $parsed }
        '^(import|cp|copy)$' { Invoke-CxImport -ArgsObj $parsed }
        '^(remove|rm|delete)$' { Invoke-CxRemove -ArgsObj $parsed }
        '^(show|info)$' { Invoke-CxShow -ArgsObj $parsed }
        '^(path)$' { Invoke-CxPath -ArgsObj $parsed }
        '^(which|current)$' { Invoke-CxWhich }
        '^(use|set|activate)$' { Invoke-CxUse -ArgsObj $parsed }
        '^(run|exec|start)$' {
            $code = Invoke-CxRun -ArgsObj $parsed
            if ($null -ne $code) { exit $code }
        }
        '^(open|window)$' { Invoke-CxOpen -ArgsObj $parsed }
        '^(edit)$' { Invoke-CxEdit -ArgsObj $parsed }
        '^(doctor|check)$' { Invoke-CxDoctor -ArgsObj $parsed }
        default {
            # Shorthand: `cx Official` == `cx use Official` if profile exists
            $maybe = $Command
            $root = Get-CxRoot
            $candidate = Join-Path $root $maybe
            if (Test-Path -LiteralPath $candidate -PathType Container) {
                $parsed2 = [pscustomobject]@{
                    Positional = @($maybe) + $parsed.Positional
                    Flags      = $parsed.Flags
                }
                Invoke-CxUse -ArgsObj $parsed2
            } else {
                Write-Host "Unknown command: $Command" -ForegroundColor Red
                Invoke-CxHelp
                exit 1
            }
        }
    }
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
