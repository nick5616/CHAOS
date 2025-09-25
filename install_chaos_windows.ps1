# CHAOS Windows Installer - Right-click and "Run with PowerShell"

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Host "CHAOS Installer requires administrator privileges." -ForegroundColor Yellow
    Write-Host "Please right-click this file and select 'Run as administrator'" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Show welcome message
Add-Type -AssemblyName System.Windows.Forms
$result = [System.Windows.Forms.MessageBox]::Show("Welcome to CHAOS Desktop Application Installer!

This will install CHAOS to your Applications folder and create shortcuts.

Click OK to continue.", "CHAOS Installer", "OKCancel", "Information")

if ($result -ne "OK") {
    Write-Host "Installation cancelled by user"
    exit 0
}

# Set installation directory
$installDir = "$env:USERPROFILE\Applications\CHAOS"
$sourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Installing CHAOS to: $installDir" -ForegroundColor Green

# Create installation directory
if (Test-Path $installDir) {
    Remove-Item $installDir -Recurse -Force
}
New-Item -ItemType Directory -Path $installDir -Force

# Copy files
Write-Host "Copying application files..." -ForegroundColor Green
Copy-Item "$sourceDir\chaos_lib" "$installDir\" -Recurse
Copy-Item "$sourceDir\desktop_app" "$installDir\" -Recurse
Copy-Item "$sourceDir\config.yaml" "$installDir\"
Copy-Item "$sourceDir\requirements.txt" "$installDir\"

# Create virtual environment
Write-Host "Setting up Python environment..." -ForegroundColor Green
Set-Location $installDir
python -m venv venv
& "$installDir\venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt

# Create launcher
Write-Host "Creating launcher..." -ForegroundColor Green
$launcherContent = @"
@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python desktop_app\main_gui.py
pause
"@
$launcherContent | Out-File -FilePath "$installDir\start_chaos.bat" -Encoding ASCII

# Create Start Menu shortcut
Write-Host "Creating Start Menu shortcut..." -ForegroundColor Green
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\CHAOS.lnk")
$Shortcut.TargetPath = "$installDir\start_chaos.bat"
$Shortcut.WorkingDirectory = $installDir
$Shortcut.Description = "CHAOS Desktop Application"
$Shortcut.Save()

# Create Desktop shortcut
$result = [System.Windows.Forms.MessageBox]::Show("Create desktop shortcut?", "CHAOS Installer", "YesNo", "Question")
if ($result -eq "Yes") {
    Write-Host "Creating desktop shortcut..." -ForegroundColor Green
    $Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\CHAOS.lnk")
    $Shortcut.TargetPath = "$installDir\start_chaos.bat"
    $Shortcut.WorkingDirectory = $installDir
    $Shortcut.Description = "CHAOS Desktop Application"
    $Shortcut.Save()
}

# Create registry entries for Add/Remove Programs
Write-Host "Creating registry entries..." -ForegroundColor Green
$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\CHAOS"
New-Item -Path $regPath -Force | Out-Null
Set-ItemProperty -Path $regPath -Name "DisplayName" -Value "CHAOS Desktop Application"
Set-ItemProperty -Path $regPath -Name "DisplayVersion" -Value "1.0"
Set-ItemProperty -Path $regPath -Name "Publisher" -Value "CHAOS Team"
Set-ItemProperty -Path $regPath -Name "InstallLocation" -Value $installDir
Set-ItemProperty -Path $regPath -Name "UninstallString" -Value "$installDir\uninstall.bat"

# Create uninstaller
Write-Host "Creating uninstaller..." -ForegroundColor Green
$uninstallerContent = @"
@echo off
echo CHAOS Desktop Application Uninstaller
echo =====================================
echo.
echo This will remove CHAOS from: $installDir
echo.
set /p confirm=Are you sure you want to uninstall CHAOS? (y/N): 
if /i not "%confirm%"=="y" (
    echo Uninstall cancelled.
    pause
    exit /b 0
)
echo.
echo Removing CHAOS installation...
if exist "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\CHAOS.lnk" del "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\CHAOS.lnk"
if exist "$env:USERPROFILE\Desktop\CHAOS.lnk" del "$env:USERPROFILE\Desktop\CHAOS.lnk"
reg delete "HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Uninstall\CHAOS" /f >nul 2>&1
if exist "$installDir" rmdir /s /q "$installDir"
echo.
echo CHAOS has been completely uninstalled.
pause
"@
$uninstallerContent | Out-File -FilePath "$installDir\uninstall.bat" -Encoding ASCII

# Show success message
[System.Windows.Forms.MessageBox]::Show("CHAOS has been successfully installed!

You can now:
• Find it in your Start Menu
• Use the desktop shortcut (if created)
• Launch it from Add/Remove Programs

The application is ready to use!", "CHAOS Installer", "OK", "Information")

Write-Host "Installation complete!" -ForegroundColor Green
Write-Host "CHAOS has been installed to: $installDir" -ForegroundColor Green
Read-Host "Press Enter to exit"
