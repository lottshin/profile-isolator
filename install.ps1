#Requires -Version 5.1
<#
.SYNOPSIS
  Install cx (Codex profile isolation) into the current user environment.

.DESCRIPTION
  1) Adds this folder to user PATH (so `cx` works in new terminals via cx.cmd)
  2) Optionally injects Import-Module into the PowerShell profile so `cx use`
     mutates the CURRENT shell's CODEX_HOME

.EXAMPLE
  .\install.ps1
  .\install.ps1 -NoProfile
  .\install.ps1 -ProfilesRoot "D:\CodexProfiles"
#>

[CmdletBinding()]
param(
    [string]$ProfilesRoot,
    [switch]$NoProfile,
    [switch]$Uninstall
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ToolDir = $PSScriptRoot
$ModulePath = Join-Path $ToolDir 'cx-profile.psm1'
$CmdPath = Join-Path $ToolDir 'cx.cmd'

if (-not (Test-Path -LiteralPath $ModulePath)) { throw "Missing $ModulePath" }
if (-not (Test-Path -LiteralPath $CmdPath)) { throw "Missing $CmdPath" }

function Get-UserPath {
    return [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Set-UserPath([string]$Value) {
    [Environment]::SetEnvironmentVariable('Path', $Value, 'User')
}

if ($Uninstall) {
    $userPath = Get-UserPath
    if ($userPath) {
        $parts = $userPath -split ';' | Where-Object { $_ -and ($_.TrimEnd('\') -ine $ToolDir.TrimEnd('\')) }
        Set-UserPath (($parts) -join ';')
        Write-Host "Removed from user PATH: $ToolDir" -ForegroundColor Green
    }

    $markerStart = '# >>> cx-profile >>>'
    $markerEnd = '# <<< cx-profile <<<'
    if (Test-Path $PROFILE) {
        $raw = Get-Content -LiteralPath $PROFILE -Raw
        if ($raw -match [regex]::Escape($markerStart)) {
            $pattern = "(?s)\r?\n?" + [regex]::Escape($markerStart) + ".*?" + [regex]::Escape($markerEnd) + "\r?\n?"
            $new = [regex]::Replace($raw, $pattern, "`r`n")
            Set-Content -LiteralPath $PROFILE -Value $new -Encoding UTF8
            Write-Host "Removed import block from $PROFILE" -ForegroundColor Green
        }
    }

    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktop 'Codex Profile Isolator.lnk'
    if (Test-Path -LiteralPath $shortcutPath) {
        Remove-Item -LiteralPath $shortcutPath -Force
        Write-Host "Removed desktop shortcut" -ForegroundColor Green
    }

    Write-Host "Uninstall done. Open a new terminal." -ForegroundColor Cyan
    return
}

# --- PATH ---
$userPath = Get-UserPath
$pathParts = @()
if ($userPath) { $pathParts = $userPath -split ';' | Where-Object { $_ } }
$already = $pathParts | Where-Object { $_.TrimEnd('\') -ieq $ToolDir.TrimEnd('\') }
if (-not $already) {
    $newPath = if ($userPath -and $userPath.Trim()) { "$userPath;$ToolDir" } else { $ToolDir }
    Set-UserPath $newPath
    Write-Host "Added to user PATH: $ToolDir" -ForegroundColor Green
} else {
    Write-Host "Already on user PATH: $ToolDir" -ForegroundColor DarkGray
}

# Make available in THIS session too
if ($env:Path -notlike "*$ToolDir*") {
    $env:Path = "$env:Path;$ToolDir"
}

# --- Profiles root ---
if ($ProfilesRoot) {
    [Environment]::SetEnvironmentVariable('CODEX_PROFILES_ROOT', $ProfilesRoot, 'User')
    $env:CODEX_PROFILES_ROOT = $ProfilesRoot
    Write-Host "CODEX_PROFILES_ROOT (user) = $ProfilesRoot" -ForegroundColor Green
    if (-not (Test-Path -LiteralPath $ProfilesRoot)) {
        New-Item -ItemType Directory -Force -Path $ProfilesRoot | Out-Null
    }
} else {
    $defaultRoot = Join-Path $env:USERPROFILE 'CodexProfiles'
    if (-not $env:CODEX_PROFILES_ROOT) {
        Write-Host "Profiles root default: $defaultRoot" -ForegroundColor DarkGray
        Write-Host "Override with: .\install.ps1 -ProfilesRoot 'D:\CodexProfiles'" -ForegroundColor DarkGray
    }
    if (-not (Test-Path -LiteralPath $defaultRoot)) {
        New-Item -ItemType Directory -Force -Path $defaultRoot | Out-Null
        Write-Host "Created $defaultRoot" -ForegroundColor Green
    }
}

# --- PowerShell profile import (so `cx use` sticks) ---
if (-not $NoProfile) {
    $markerStart = '# >>> cx-profile >>>'
    $markerEnd = '# <<< cx-profile <<<'
    $block = @"
$markerStart
# Codex profile isolation (cx) — Import-Module so `cx use` sets CODEX_HOME in this shell
`$env:Path = (`$env:Path -split ';' | Where-Object { `$_ } ) + '$($ToolDir.Replace("'","''"))' -join ';'
Import-Module '$($ModulePath.Replace("'","''"))' -Force
$markerEnd
"@

    $profileDir = Split-Path -Parent $PROFILE
    if (-not (Test-Path -LiteralPath $profileDir)) {
        New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
    }
    if (-not (Test-Path -LiteralPath $PROFILE)) {
        Set-Content -LiteralPath $PROFILE -Value $block -Encoding UTF8
        Write-Host "Created PowerShell profile: $PROFILE" -ForegroundColor Green
    } else {
        $raw = Get-Content -LiteralPath $PROFILE -Raw
        if ($raw -match [regex]::Escape($markerStart)) {
            $pattern = "(?s)" + [regex]::Escape($markerStart) + ".*?" + [regex]::Escape($markerEnd)
            $new = [regex]::Replace($raw, $pattern, $block.TrimEnd())
            Set-Content -LiteralPath $PROFILE -Value $new -Encoding UTF8
            Write-Host "Updated cx block in $PROFILE" -ForegroundColor Green
        } else {
            Add-Content -LiteralPath $PROFILE -Value "`r`n$block" -Encoding UTF8
            Write-Host "Appended cx block to $PROFILE" -ForegroundColor Green
        }
    }

    # Load now
    Import-Module $ModulePath -Force
    Write-Host "Module loaded in current session." -ForegroundColor Green
} else {
    Write-Host "Skipped PowerShell profile injection (-NoProfile)." -ForegroundColor Yellow
    Write-Host "Note: without the module, 'cx use' in a child process won't stick; prefer 'cx run' / 'cx open'." -ForegroundColor Yellow
}

Write-Host ""
# Desktop shortcut for GUI
try {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $shortcutPath = Join-Path $desktop 'Codex Profile Isolator.lnk'
    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut($shortcutPath)
    $sc.TargetPath = 'powershell.exe'
    $sc.Arguments = "-NoProfile -ExecutionPolicy Bypass -STA -File `"$(Join-Path $ToolDir 'cx-gui.ps1')`""
    $sc.WorkingDirectory = $ToolDir
    $sc.WindowStyle = 7  # minimized console host
    $sc.Description = 'Codex Profile Isolator GUI'
    $sc.Save()
    Write-Host "Desktop shortcut: $shortcutPath" -ForegroundColor Green
} catch {
    Write-Host "Desktop shortcut skipped: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Install complete." -ForegroundColor Cyan
Write-Host "Try:" -ForegroundColor Cyan
Write-Host "  cx-gui          # graphical UI"
Write-Host "  cx init"
Write-Host "  cx new Official -FromCurrent"
Write-Host "  cx list"
Write-Host "  cx use Official"
Write-Host "  cx run Official"
Write-Host ""
Write-Host "Open a NEW terminal so PATH / profile take effect everywhere." -ForegroundColor DarkGray
