# bootstrap.ps1 - Set up Claude Code with context-reset on a fresh Windows machine
# Run: iwr -useb https://raw.githubusercontent.com/grobomo/context-reset/main/scripts/bootstrap.ps1 | iex
#
# What it does:
#   1. Checks prerequisites (Python 3.8+, Node.js, Windows Terminal)
#   2. Installs Claude Code CLI (npm)
#   3. Installs context-reset (pip)
#   4. Configures the stop hook in ~/.claude/settings.json
#
# Safe to re-run -- skips already-installed components.

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n=> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "   OK: $msg" -ForegroundColor Green }
function Write-Skip($msg) { Write-Host "   SKIP: $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "   FAIL: $msg" -ForegroundColor Red }

# --- Prerequisites ---

Write-Step "Checking Python"
try {
    $pyVer = python --version 2>&1
    if ($pyVer -match 'Python (\d+)\.(\d+)') {
        $major = [int]$Matches[1]; $minor = [int]$Matches[2]
        if ($major -ge 3 -and $minor -ge 8) {
            Write-Ok $pyVer
        } else {
            Write-Fail "$pyVer -- need Python 3.8+. Install from https://python.org"
            exit 1
        }
    }
} catch {
    Write-Fail "Python not found. Install from https://python.org"
    exit 1
}

Write-Step "Checking Node.js"
try {
    $nodeVer = node --version 2>&1
    Write-Ok "Node $nodeVer"
} catch {
    Write-Fail "Node.js not found. Install from https://nodejs.org"
    exit 1
}

Write-Step "Checking Windows Terminal"
$wt = Get-Command wt -ErrorAction SilentlyContinue
if ($wt) {
    Write-Ok "Windows Terminal found"
} else {
    Write-Skip "Windows Terminal not found -- context-reset tab features will not work"
    Write-Host "         Install from Microsoft Store or winget install Microsoft.WindowsTerminal"
}

# --- Claude Code CLI ---

Write-Step "Checking Claude Code CLI"
$claude = Get-Command claude -ErrorAction SilentlyContinue
if ($claude) {
    Write-Skip "Claude Code already installed"
} else {
    Write-Host "   Installing Claude Code..."
    npm install -g @anthropic-ai/claude-code
    Write-Ok "Claude Code installed"
}

# --- context-reset ---

Write-Step "Installing context-reset"
$ErrorActionPreference = "Continue"
$existing = pip show claude-context-reset 2>&1
if ("$existing" -match "Name: claude-context-reset") {
    Write-Host "   Upgrading..."
    pip install --upgrade git+https://github.com/grobomo/context-reset 2>&1 | Out-Null
    Write-Ok "context-reset upgraded"
} else {
    pip install git+https://github.com/grobomo/context-reset 2>&1 | Out-Null
    Write-Ok "context-reset installed"
}
$ErrorActionPreference = "Stop"

# Verify CLI entry point
try {
    $help = new-session --help 2>&1
    Write-Ok "new-session CLI works"
} catch {
    Write-Fail "new-session CLI not found in PATH - check pip Scripts directory"
    exit 1
}

# --- Configure stop hook (uses Python to avoid PowerShell JSON/encoding quirks) ---

Write-Step "Configuring Claude Code stop hook"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$result = python (Join-Path $scriptDir "configure_hook.py") 2>&1

if ($result -eq "SKIP") {
    Write-Skip "Stop hook already configured"
} elseif ($result -eq "ADDED") {
    Write-Ok "Stop hook added to existing settings.json"
} elseif ($result -eq "CREATED") {
    Write-Ok "Created settings.json with stop hook"
} else {
    Write-Fail "Failed to configure stop hook"
}

# --- Done ---

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Run 'claude' in any project directory to start a session"
Write-Host "  2. When context fills up, Claude will automatically reset to a fresh tab"
Write-Host "  3. TODO.md and SESSION_STATE.md carry context between sessions"
Write-Host ""
