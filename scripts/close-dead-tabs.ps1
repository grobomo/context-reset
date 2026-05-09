# close-dead-tabs.ps1 — Close WT tabs whose child process has exited.
#
# Dead tabs show "process exited with code N" and have no wsl.exe child.
# This script finds OpenConsole processes without wsl.exe children and
# terminates them, which causes WT to close those tabs.
#
# Usage (from WSL): powershell.exe -NoProfile -File close-dead-tabs.ps1
# Usage (from PS):  .\close-dead-tabs.ps1

$ErrorActionPreference = "SilentlyContinue"

# Get all OpenConsole processes (one per WT tab/pane)
$openConsoles = Get-Process OpenConsole -ErrorAction SilentlyContinue

if (-not $openConsoles) {
    Write-Host "No OpenConsole processes found."
    exit 0
}

$killed = 0
foreach ($oc in $openConsoles) {
    # Check if this OpenConsole has any wsl.exe or bash child
    $children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $oc.Id }
    $hasWsl = $children | Where-Object { $_.Name -match "wsl|bash|ubuntu|cmd|powershell|pwsh|node|claude" }

    if (-not $hasWsl) {
        # No live child process — this tab is dead
        $age = (Get-Date) - $oc.StartTime
        Write-Host "Closing dead tab: OpenConsole PID=$($oc.Id), started=$($oc.StartTime.ToString('HH:mm')), age=$([int]$age.TotalMinutes)min"
        Stop-Process -Id $oc.Id -Force
        $killed++
    }
}

if ($killed -eq 0) {
    Write-Host "No dead tabs found. All tabs have active child processes."
} else {
    Write-Host "Closed $killed dead tab(s)."
}
