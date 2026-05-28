$ErrorActionPreference = "Stop"

$trackerProcesses = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'pythonw.exe'" |
  Where-Object { [string]$_.CommandLine -match "PokemonOverlay\\tracker\\main.py" }

if (-not $trackerProcesses) {
  Write-Host "No tracker process is currently running."
  exit 0
}

foreach ($proc in $trackerProcesses) {
  $trackerPid = [int]$proc.ProcessId
  Write-Host "Stopping tracker PID=$trackerPid"
  Stop-Process -Id $trackerPid -Force -ErrorAction SilentlyContinue
}

$listener = Get-NetTCPConnection -State Listen -LocalAddress "127.0.0.1" -LocalPort 8765 -ErrorAction SilentlyContinue |
  Select-Object -First 1
if ($listener) {
  $ownerPid = [int]$listener.OwningProcess
  $ownerProcess = Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
  if ($ownerProcess -and ([string]$ownerProcess.ProcessName) -in @("python", "pythonw")) {
    Write-Host "Stopping websocket python listener PID=$ownerPid"
    Stop-Process -Id $ownerPid -Force -ErrorAction SilentlyContinue
  }
}

Write-Host "Tracker stopped."