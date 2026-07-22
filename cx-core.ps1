#Requires -Version 5.1
# Shared core for cx CLI and cx GUI. Dot-source this file; do not execute directly.

Set-StrictMode -Version Latest

function Get-CxRoot {
    if ($env:CODEX_PROFILES_ROOT -and $env:CODEX_PROFILES_ROOT.Trim()) {
        return [System.IO.Path]::GetFullPath($env:CODEX_PROFILES_ROOT.Trim())
    }
    return (Join-Path $env:USERPROFILE 'CodexProfiles')
}

function Get-DefaultCodexHome {
    return (Join-Path $env:USERPROFILE '.codex')
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

function Get-ProfilePath {
    param([Parameter(Mandatory)][string]$Name)
    return (Join-Path (Get-CxRoot) (Get-SafeProfileName $Name))
}

function Assert-ProfileExists {
    param([Parameter(Mandatory)][string]$Name)
    $path = Get-ProfilePath $Name
    if (-not (Test-Path -LiteralPath $path -PathType Container)) {
        throw "Profile '$Name' not found at $path"
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

function Get-ConfigSummary {
    param([string]$ProfileDir)
    $cfg = Join-Path $ProfileDir 'config.toml'
    $auth = Join-Path $ProfileDir 'auth.json'
    $model = $null
    $provider = $null
    $baseUrl = $null
    $providerName = $null
    $hasAuth = Test-Path -LiteralPath $auth
    $hasCfg = Test-Path -LiteralPath $cfg
    $hasCatalog = $false

    if ($hasCfg) {
        $text = Get-Content -LiteralPath $cfg -Raw -ErrorAction SilentlyContinue
        if ($text) {
            if ($text -match '(?m)^\s*model\s*=\s*"([^"]+)"') { $model = $Matches[1] }
            if ($text -match '(?m)^\s*model_provider\s*=\s*"([^"]+)"') { $provider = $Matches[1] }
            if ($text -match '(?m)^\s*base_url\s*=\s*"([^"]+)"') { $baseUrl = $Matches[1] }
            if ($text -match '(?m)^\s*name\s*=\s*"([^"]+)"') { $providerName = $Matches[1] }
            if ($text -match 'model_catalog_json') { $hasCatalog = $true }
        }
    }

    [pscustomobject]@{
        HasConfig    = $hasCfg
        HasAuth      = $hasAuth
        Model        = $model
        Provider     = $provider
        ProviderName = $providerName
        BaseUrl      = $baseUrl
        HasCatalog   = $hasCatalog
    }
}

function Get-CxProfiles {
    $root = Get-CxRoot
    if (-not (Test-Path -LiteralPath $root)) { return @() }

    $dirs = Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch '^\.' } |
        Sort-Object Name

    $current = $env:CODEX_HOME
    $list = foreach ($d in @($dirs)) {
        $s = Get-ConfigSummary $d.FullName
        $isActive = $false
        if ($current) {
            try {
                $isActive = ([IO.Path]::GetFullPath($current).TrimEnd('\') -ieq $d.FullName.TrimEnd('\'))
            } catch { $isActive = $false }
        }
        [pscustomobject]@{
            Name         = $d.Name
            Path         = $d.FullName
            Model        = $(if ($s.Model) { $s.Model } else { '' })
            Provider     = $(if ($s.Provider) { $s.Provider } else { '' })
            ProviderName = $(if ($s.ProviderName) { $s.ProviderName } else { '' })
            BaseUrl      = $(if ($s.BaseUrl) { $s.BaseUrl } else { '' })
            HasConfig    = $s.HasConfig
            HasAuth      = $s.HasAuth
            HasCatalog   = $s.HasCatalog
            IsActive     = $isActive
        }
    }
    return @($list)
}

function Initialize-CxRoot {
    $root = Get-CxRoot
    if (-not (Test-Path -LiteralPath $root)) {
        New-Item -ItemType Directory -Force -Path $root | Out-Null
    }
    return $root
}

function Sanitize-CodexConfigText {
    param([string]$Text, [switch]$Quiet)
    if (-not $Text) { return $Text }
    $lines = $Text -split "`r?`n"
    $kept = foreach ($line in $lines) {
        if ($line -match '^\s*model_catalog_json\s*=') {
            if (-not $Quiet) {
                Write-Verbose "sanitize removed: $($line.Trim())"
            }
            continue
        }
        $line
    }
    return ($kept -join "`n")
}

function Write-Utf8NoBom {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Content)
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($Path, $Content, $utf8)
}

function Copy-CodexProfileFiles {
    param(
        [Parameter(Mandatory)][string]$SourceDir,
        [Parameter(Mandatory)][string]$DestDir,
        [switch]$Force,
        [switch]$Quiet
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
        throw "config.toml already exists in $DestDir"
    }
    if ((Test-Path -LiteralPath $authDst) -and -not $Force) {
        throw "auth.json already exists in $DestDir"
    }

    if (Test-Path -LiteralPath $cfgSrc) {
        $raw = Get-Content -LiteralPath $cfgSrc -Raw
        $clean = Sanitize-CodexConfigText $raw -Quiet:$Quiet
        Write-Utf8NoBom -Path $cfgDst -Content $clean
    }

    if (Test-Path -LiteralPath $authSrc) {
        Copy-Item -LiteralPath $authSrc -Destination $authDst -Force
    }
}

function Write-StubConfig {
    param([Parameter(Mandatory)][string]$DestDir)
    New-Item -ItemType Directory -Force -Path $DestDir | Out-Null
    $cfg = Join-Path $DestDir 'config.toml'
    $auth = Join-Path $DestDir 'auth.json'

    if (-not (Test-Path -LiteralPath $cfg)) {
        $stub = @"
# Codex profile config - edit me
# model_provider = "custom"
# model = "gpt-5.5"
# model_reasoning_effort = "high"
#
# [model_providers.custom]
# name = "MyProvider"
# wire_api = "responses"
# base_url = "https://api.example.com/v1"
# requires_openai_auth = true
"@
        Write-Utf8NoBom -Path $cfg -Content ($stub.TrimStart() + "`n")
    }
    if (-not (Test-Path -LiteralPath $auth)) {
        $authStub = @"
{
  "OPENAI_API_KEY": "sk-REPLACE_ME"
}
"@
        Write-Utf8NoBom -Path $auth -Content ($authStub.TrimStart() + "`n")
    }
}

function New-CxProfile {
    param(
        [Parameter(Mandatory)][string]$Name,
        [switch]$FromCurrent,
        [string]$SourceDir,
        [switch]$Force
    )
    $safe = Get-SafeProfileName $Name
    $path = Get-ProfilePath $safe
    [void](Initialize-CxRoot)

    if ((Test-Path -LiteralPath $path) -and -not $Force) {
        throw "Profile already exists: $path"
    }
    if ((Test-Path -LiteralPath $path) -and $Force) {
        Remove-Item -LiteralPath $path -Recurse -Force
    }

    if ($FromCurrent) {
        Copy-CodexProfileFiles -SourceDir (Get-DefaultCodexHome) -DestDir $path -Force -Quiet
    } elseif ($SourceDir) {
        Copy-CodexProfileFiles -SourceDir $SourceDir -DestDir $path -Force -Quiet
    } else {
        Write-StubConfig -DestDir $path
    }
    return $path
}

function Remove-CxProfile {
    param([Parameter(Mandatory)][string]$Name)
    $path = Assert-ProfileExists $Name
    Remove-Item -LiteralPath $path -Recurse -Force
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

function Get-SafeLaunchDirectory {
    param([string]$Preferred)
    if ($Preferred -and (Test-Path -LiteralPath $Preferred -PathType Container)) {
        return (Resolve-Path -LiteralPath $Preferred).Path
    }
    $cwd = (Get-Location).Path
    $home = [IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\')
    if ([IO.Path]::GetFullPath($cwd).TrimEnd('\') -ieq $home) {
        $desktop = Join-Path $env:USERPROFILE 'Desktop'
        if (Test-Path $desktop) { return $desktop }
        return $env:TEMP
    }
    return $cwd
}

function Start-CxProfileSession {
    param(
        [Parameter(Mandatory)][string]$Name,
        [string]$WorkDir,
        [switch]$RunCodex,
        [string[]]$CodexArgs
    )
    $path = Assert-ProfileExists $Name
    $wd = Get-SafeLaunchDirectory -Preferred $WorkDir

    if ($RunCodex) {
        $codex = Find-CodexCommand
        if (-not $codex) { throw 'codex command not found in PATH' }

        $argLine = if ($CodexArgs -and $CodexArgs.Count -gt 0) {
            ($CodexArgs | ForEach-Object {
                if ($_ -match '\s') { '"{0}"' -f ($_ -replace '"', '`"') } else { $_ }
            }) -join ' '
        } else { '' }

        $ps = @"
`$env:CODEX_HOME = '$($path.Replace("'","''"))'
Set-Location -LiteralPath '$($wd.Replace("'","''"))'
Write-Host ('[cx] profile = $Name') -ForegroundColor Green
Write-Host ('[cx] CODEX_HOME = ' + `$env:CODEX_HOME) -ForegroundColor DarkGray
Write-Host ('[cx] CWD = ' + (Get-Location)) -ForegroundColor DarkGray
& '$($codex.Replace("'","''"))' $argLine
"@
        Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoExit', '-NoLogo', '-Command', $ps) | Out-Null
    } else {
        $ps = @"
`$env:CODEX_HOME = '$($path.Replace("'","''"))'
Set-Location -LiteralPath '$($wd.Replace("'","''"))'
Write-Host ('[cx] CODEX_HOME=' + `$env:CODEX_HOME) -ForegroundColor Green
Write-Host ('[cx] profile   = $Name') -ForegroundColor DarkGray
Write-Host 'Type: codex' -ForegroundColor DarkGray
"@
        Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoExit', '-NoLogo', '-Command', $ps) | Out-Null
    }
}

function Get-CxDoctorReport {
    param([string]$Name)
    $lines = New-Object System.Collections.Generic.List[string]
    $root = Get-CxRoot
    $homeCodex = Get-DefaultCodexHome

    [void]$lines.Add("Profiles root : $root")
    [void]$lines.Add("Default codex : $homeCodex")
    [void]$lines.Add("CODEX_HOME    : $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { '(unset)' })")
    [void]$lines.Add("")

    $codex = Find-CodexCommand
    if ($codex) { [void]$lines.Add("[ok] codex found: $codex") }
    else { [void]$lines.Add("[!!] codex not found in PATH") }

    if (Test-Path -LiteralPath $root) { [void]$lines.Add("[ok] profiles root exists") }
    else { [void]$lines.Add("[!!] profiles root missing") }

    if (Test-IsUnderPath -Child $root -Parent $homeCodex) {
        [void]$lines.Add("[!!] profiles root is under ~/.codex - high risk")
    } else {
        [void]$lines.Add("[ok] profiles root outside ~/.codex")
    }

    if ($Name) {
        $path = Assert-ProfileExists $Name
        $s = Get-ConfigSummary $path
        [void]$lines.Add("")
        [void]$lines.Add("--- profile: $Name ---")
        [void]$lines.Add($(if ($s.HasConfig) { "[ok] config.toml" } else { "[!!] missing config.toml" }))
        [void]$lines.Add($(if ($s.HasAuth) { "[ok] auth.json" } else { "[!!] missing auth.json" }))
        [void]$lines.Add($(if ($s.HasCatalog) { "[!!] contains model_catalog_json" } else { "[ok] no model_catalog_json" }))
        if ($s.Model) { [void]$lines.Add("[ok] model = $($s.Model)") }
        if ($s.BaseUrl) { [void]$lines.Add("[ok] base_url = $($s.BaseUrl)") }
    }

    return ($lines -join "`r`n")
}

function Read-ProfileFile {
    param(
        [Parameter(Mandatory)][string]$Name,
        [ValidateSet('config', 'auth')][string]$Which = 'config'
    )
    $path = Assert-ProfileExists $Name
    $file = if ($Which -eq 'config') { Join-Path $path 'config.toml' } else { Join-Path $path 'auth.json' }
    if (-not (Test-Path -LiteralPath $file)) { return '' }
    return (Get-Content -LiteralPath $file -Raw)
}

function Save-ProfileFile {
    param(
        [Parameter(Mandatory)][string]$Name,
        [ValidateSet('config', 'auth')][string]$Which = 'config',
        [Parameter(Mandatory)][AllowEmptyString()][string]$Content
    )
    $path = Assert-ProfileExists $Name
    $file = if ($Which -eq 'config') {
        Join-Path $path 'config.toml'
    } else {
        Join-Path $path 'auth.json'
    }
    $toWrite = if ($Which -eq 'config') {
        Sanitize-CodexConfigText $Content -Quiet
    } else {
        $Content
    }
    Write-Utf8NoBom -Path $file -Content $toWrite
    return $file
}

function Mask-ApiKey {
    param([string]$Text)
    if (-not $Text) { return $Text }
    return [regex]::Replace($Text, '("OPENAI_API_KEY"\s*:\s*")([^"]{8})[^"]*(")', '$1$2...$3')
}
