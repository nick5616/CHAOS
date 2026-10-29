# CHAOS setup for Windows. Double-click setup.bat rather than running this directly.
# Finds (or installs) Python 3.10+, then hands off to scripts\install.py.
# Extra arguments (e.g. --desktop-shortcut) are passed through to install.py.

Set-Location $PSScriptRoot

function Test-Python([string]$exe, [string[]]$pyArgs = @()) {
    # True if this runs a real Python 3.10+. Rejects the Microsoft Store
    # "python.exe" stub, which exists on PATH but isn't Python.
    try {
        $out = & $exe $pyArgs -c "import sys; print(sys.version_info >= (3, 10))" 2>$null
        return $LASTEXITCODE -eq 0 -and $out -eq "True"
    } catch {
        return $false
    }
}

function Find-Python {
    # 3.12 first: it's what CHAOS is developed against and every dependency has wheels for it.
    foreach ($v in "3.12", "3.11", "3.13", "3.10") {
        if (Test-Python "py" @("-$v")) { return @{ Exe = "py"; Args = @("-$v") } }
    }
    foreach ($exe in "python", "python3", "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe") {
        if (Test-Python $exe) { return @{ Exe = $exe; Args = @() } }
    }
    return $null
}

Write-Host "CHAOS setup" -ForegroundColor Cyan
Write-Host ""

$python = Find-Python
if (-not $python) {
    Write-Host "Python 3.10+ not found." -ForegroundColor Yellow
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Installing Python 3.12 with winget (just for your user, no admin needed)..."
        winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
        $python = Find-Python
    }
    if (-not $python) {
        Write-Host ""
        Write-Host "Couldn't install Python automatically." -ForegroundColor Red
        Write-Host "Install Python 3.12 from https://www.python.org/downloads/ and run setup again."
        exit 1
    }
}

& $python.Exe $python.Args "scripts\install.py" $args
exit $LASTEXITCODE
