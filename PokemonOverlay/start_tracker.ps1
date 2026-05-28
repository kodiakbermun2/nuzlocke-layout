param(
  [switch]$Debug
)

$ErrorActionPreference = "Stop"

$overlayRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Split-Path -Parent $overlayRoot
$trackerEntry = Join-Path $overlayRoot "tracker/main.py"
$configPath = Join-Path $overlayRoot "config.json"
$lockPath = Join-Path $overlayRoot "tracker/tracker.instance.lock"

if (-not (Test-Path $trackerEntry)) {
  throw "Tracker entry not found at $trackerEntry"
}

if (-not (Test-Path $configPath)) {
  throw "Config file not found at $configPath"
}

function Get-TrackerCommandLine {
  param([int]$ProcessId)
  $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
  if (-not $proc) {
    return ""
  }
  return [string]$proc.CommandLine
}

function Stop-TrackerProcessById {
  param([int]$ProcessId)
  if ($ProcessId -le 0) {
    return
  }
  Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

$trackerProcessList = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
  Where-Object { [string]$_.CommandLine -match "PokemonOverlay\\tracker\\main.py" }

foreach ($proc in $trackerProcessList) {
  Write-Host "Stopping existing tracker process PID=$($proc.ProcessId)"
  Stop-TrackerProcessById -ProcessId ([int]$proc.ProcessId)
}

$listeners = Get-NetTCPConnection -State Listen -LocalAddress "127.0.0.1" -LocalPort 8765 -ErrorAction SilentlyContinue
if ($listeners) {
  $listener = $listeners | Select-Object -First 1
  $ownerPid = [int]$listener.OwningProcess
  $ownerCommandLine = Get-TrackerCommandLine -ProcessId $ownerPid
  $ownerProcess = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
  $ownerName = if ($ownerProcess) { [string]$ownerProcess.ProcessName } else { "" }

  if ($ownerCommandLine -match "PokemonOverlay\\tracker\\main.py") {
    Write-Host "Port 8765 is owned by an existing tracker process PID=$ownerPid. Stopping it."
    Stop-TrackerProcessById -ProcessId $ownerPid
  } elseif ($ownerName -in @("python", "pythonw")) {
    Write-Host "Port 8765 is owned by PID=$ownerPid ($ownerName) with unavailable command line. Stopping it."
    Stop-TrackerProcessById -ProcessId $ownerPid
  } else {
    throw "Port 8765 is in use by PID=$ownerPid ($ownerName). Command line: $ownerCommandLine"
  }
}

if (Test-Path $lockPath) {
  Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
}

$pythonCandidates = @(
  (Join-Path $workspaceRoot ".venv/Scripts/python.exe"),
  (Join-Path $overlayRoot ".venv/Scripts/python.exe")
)

$pythonExe = $null
foreach ($candidate in $pythonCandidates) {
  if (Test-Path $candidate) {
    $pythonExe = $candidate
    break
  }
}

if (-not $pythonExe) {
  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCmd) {
    $pythonExe = $pythonCmd.Source
  }
}

if (-not $pythonExe) {
  throw "Could not find a Python executable. Activate your venv or install Python first."
}

$launchParameters = @($trackerEntry, "--config", $configPath)
if ($Debug) {
  $launchParameters += "--debug"
}

Write-Host "Starting tracker with $pythonExe"
Write-Host "Config: $configPath"

& $pythonExe @launchParameters