# One-command installer for skills-manager (PyPI: skill-control-plane), Windows.
#
#   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/udayvarmora07/skills-manager/main/install.ps1 | iex"
#
# With options:
#
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/udayvarmora07/skills-manager/main/install.ps1))) -WithTiktoken
#
# Order of preference: `uv tool install` (uv also supplies Python), then
# `pipx install`, then a private virtual environment under
# %LOCALAPPDATA%\skill-control-plane\venv using the first Python >= 3.11.
#
# It never edits your PATH or profile, downloads another installer, or touches
# your skills or the manager's data directory. Uninstall leaves that data alone.

[CmdletBinding()]
param(
    [string]$Method = $env:SKILLS_MGR_INSTALL_METHOD,
    [string]$Version = '',
    [switch]$Source,
    [string]$From = '',
    [switch]$WithTiktoken,
    [string]$Prefix = $env:SKILLS_MGR_INSTALL_PREFIX,
    [switch]$DryRun,
    [switch]$Uninstall,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3

$Dist = 'skill-control-plane'
$Command = 'skills-mgr'
$SourceArchive = 'https://github.com/udayvarmora07/skills-manager/archive/refs/heads/main.tar.gz'

function Say([string]$Text) { Write-Host "skills-mgr install: $Text" }
function Fail([string]$Text) { throw "skills-mgr install: error: $Text" }
function Have([string]$Name) { [bool](Get-Command $Name -ErrorAction SilentlyContinue) }

function Invoke-Step {
    param([string]$Exe, [string[]]$Arguments)
    Write-Host ('+ ' + (@($Exe) + $Arguments -join ' '))
    if (-not $DryRun) {
        & $Exe @Arguments
        if ($LASTEXITCODE -ne 0) { Fail "'$Exe' exited with code $LASTEXITCODE" }
    }
}

function Find-Python {
    # Windows PowerShell 5.1 turns redirected native stderr into an error
    # record; under 'Stop' that would abort the probe instead of skipping it.
    $ErrorActionPreference = 'Continue'
    $check = 'import sys; sys.exit(sys.version_info < (3, 11))'
    if (Have 'py') {
        foreach ($v in '3.14', '3.13', '3.12', '3.11') {
            & py "-$v" -c $check 2>$null
            if ($LASTEXITCODE -eq 0) {
                return (& py "-$v" -c 'import sys; print(sys.executable)').Trim()
            }
        }
    }
    foreach ($name in 'python', 'python3') {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) {
            & $cmd.Source -c $check 2>$null
            if ($LASTEXITCODE -eq 0) { return $cmd.Source }
        }
    }
    return $null
}

function Get-Exe([string]$Dir, [string]$Name) {
    $exe = Join-Path $Dir "$Name.exe"
    if (Test-Path $exe) { return $exe }
    return (Join-Path $Dir $Name)
}

function Get-VenvBin([string]$Root) {
    if (Test-Path (Join-Path $Root 'Scripts')) { return (Join-Path $Root 'Scripts') }
    return (Join-Path $Root 'bin')
}

function Test-Venv([string]$Root) {
    (Test-Path (Join-Path $Root 'pyvenv.cfg'))
}

if ($Help) {
    @'
Install skills-manager (the skills-mgr command) in one step.

  -Method M       uv, pipx or venv (default: the first one available)
  -Version V      install this PyPI release instead of the latest
  -Source         install the current GitHub main branch instead of PyPI
  -From SPEC      install from any pip spec: a local checkout, a URL, a wheel
  -WithTiktoken   also install tiktoken for exact token counts
  -Prefix DIR     venv method: where the environment lives
  -DryRun         print the commands, change nothing
  -Uninstall      remove what this script installed (your skills stay)
'@ | Write-Host
    return
}

if ($Method -and @('uv', 'pipx', 'venv') -notcontains $Method) {
    Fail "-Method must be uv, pipx or venv, got '$Method'"
}

if (-not $Prefix) {
    $base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME '.local/share' }
    $Prefix = Join-Path $base 'skill-control-plane/venv'
}
$Prefix = [System.IO.Path]::GetFullPath($Prefix)

$Spec = $Dist
if ($Source) { $Spec = $SourceArchive }
if ($From) { $Spec = $From }
if ($Version) {
    if ($Source -or $From) { Fail '-Version cannot be combined with -Source or -From' }
    if ($Version -notmatch '^[0-9A-Za-z][0-9A-Za-z.+!-]*$') { Fail "invalid -Version '$Version'" }
    $Spec = "$Dist==$Version"
}
if ($Spec.StartsWith('-')) { Fail "a package spec cannot start with '-'" }

if ($Uninstall) {
    $ErrorActionPreference = 'Continue'
    $removed = $false
    if ((-not $Method -or $Method -eq 'uv') -and (Have 'uv')) {
        if ((& uv tool list 2>$null) -match "^$Dist ") { Invoke-Step 'uv' @('tool', 'uninstall', $Dist); $removed = $true }
    }
    if ((-not $Method -or $Method -eq 'pipx') -and (Have 'pipx')) {
        if ((& pipx list --short 2>$null) -match "^$Dist ") { Invoke-Step 'pipx' @('uninstall', $Dist); $removed = $true }
    }
    if ((-not $Method -or $Method -eq 'venv') -and (Test-Venv $Prefix)) {
        Write-Host "+ Remove-Item -Recurse -Force $Prefix"
        if (-not $DryRun) { Remove-Item -Recurse -Force $Prefix }
        $removed = $true
    }
    if ($removed) { Say "removed. Your skills and the manager's data directory were not touched." }
    else { Say 'nothing installed by this script was found' }
    return
}

if (-not $Method) {
    if (Have 'uv') { $Method = 'uv' } elseif (Have 'pipx') { $Method = 'pipx' } else { $Method = 'venv' }
}
Say "installing $Spec with $Method"

$installed = $null
switch ($Method) {
    'uv' {
        if (-not (Have 'uv')) { Fail 'uv is not on PATH' }
        $uvArgs = @('tool', 'install', '--force', '--python', '>=3.11')
        if ($WithTiktoken) { $uvArgs += @('--with', 'tiktoken') }
        Invoke-Step 'uv' ($uvArgs + @($Spec))
    }
    'pipx' {
        if (-not (Have 'pipx')) { Fail 'pipx is not on PATH' }
        $python = Find-Python
        $pipxArgs = @('install', '--force')
        if ($python) { $pipxArgs += @('--python', $python) }
        Invoke-Step 'pipx' ($pipxArgs + @($Spec))
        if ($WithTiktoken) { Invoke-Step 'pipx' @('inject', $Dist, 'tiktoken') }
    }
    'venv' {
        $python = Find-Python
        if (-not $python) {
            Fail 'no Python 3.11 or newer found. Install one from python.org, or install uv (https://docs.astral.sh/uv/) and run this again: uv fetches Python for you.'
        }
        Say "using $python"
        if ((Test-Path $Prefix) -and -not (Test-Venv $Prefix)) {
            Fail "$Prefix exists and is not a virtual environment; refusing to touch it"
        }
        if (-not (Test-Path $Prefix)) { Invoke-Step $python @('-m', 'venv', $Prefix) }
        $bin = Get-VenvBin $Prefix
        $venvPython = Get-Exe $bin 'python'
        $pipArgs = @('-m', 'pip', 'install', '--upgrade', '--disable-pip-version-check', $Spec)
        if ($WithTiktoken) { $pipArgs += 'tiktoken' }
        Invoke-Step $venvPython $pipArgs
        $installed = Get-Exe $bin $Command
    }
}

if ($DryRun) { Say 'dry run: nothing was changed'; return }

if (-not $installed) {
    $cmd = Get-Command $Command -ErrorAction SilentlyContinue
    if ($cmd) { $installed = $cmd.Source }
}
if ($installed) {
    Say ('installed: ' + (& $installed --version))
}
if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
    switch ($Method) {
        'uv' { Say "run 'uv tool update-shell' once, then open a new terminal" }
        'pipx' { Say "run 'pipx ensurepath' once, then open a new terminal" }
        'venv' { Say "skills-mgr is in $(Get-VenvBin $Prefix); add that folder to your PATH" }
    }
}
@'

Next steps:
  skills-mgr scopes        # see every agent's skill folder this tool found
  skills-mgr doctor        # health check, changes nothing
  skills-mgr webui         # open the local web UI on 127.0.0.1

Docs: https://github.com/udayvarmora07/skills-manager#readme
'@ | Write-Host
