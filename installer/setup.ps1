# Yapper Professional Installer
# Modern GUI installer with setup options
# Copyright (c) 2026 Cloudelipute

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName Microsoft.VisualBasic

[System.Windows.Forms.Application]::EnableVisualStyles()

# Configuration
$PythonVersion = "3.11.9"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$ScriptDir = Split-Path -Parent $PSScriptRoot
$InstallDir = Join-Path $env:LOCALAPPDATA "Yapper"
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$StartupPath = [Environment]::GetFolderPath("Startup")

$Packages = @(
    @{Name="openai"; Display="OpenAI API Client"},
    @{Name="keyboard"; Display="Keyboard Hotkeys"},
    @{Name="pyaudio"; Display="Audio Recording"},
    @{Name="pystray"; Display="System Tray"},
    @{Name="Pillow"; Display="Image Processing"},
    @{Name="customtkinter"; Display="Modern UI"}
)

# Colors - Modern Dark Theme
$BgDark = [System.Drawing.Color]::FromArgb(13, 13, 18)
$BgCard = [System.Drawing.Color]::FromArgb(22, 22, 30)
$BgInput = [System.Drawing.Color]::FromArgb(30, 30, 40)
$Accent = [System.Drawing.Color]::FromArgb(99, 102, 241)
$AccentLight = [System.Drawing.Color]::FromArgb(129, 140, 248)
$TextPrimary = [System.Drawing.Color]::White
$TextSecondary = [System.Drawing.Color]::FromArgb(161, 161, 170)
$TextMuted = [System.Drawing.Color]::FromArgb(113, 113, 122)
$Success = [System.Drawing.Color]::FromArgb(34, 197, 94)
$Border = [System.Drawing.Color]::FromArgb(39, 39, 42)

# State
$script:CurrentStep = 0
$script:CreateDesktopShortcut = $true
$script:StartWithWindows = $false
$script:InstallPath = $InstallDir

# Create main form
$form = New-Object System.Windows.Forms.Form
$form.Text = "Yapper Setup"
$form.Size = New-Object System.Drawing.Size(600, 700)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedSingle"
$form.MaximizeBox = $false
$form.BackColor = $BgDark
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)

# Try to set icon
$iconPath = Join-Path $ScriptDir "yapper.ico"
if (Test-Path $iconPath) {
    $form.Icon = New-Object System.Drawing.Icon($iconPath)
}

# ============== STEP PANELS ==============

# Create panel container
$panelContainer = New-Object System.Windows.Forms.Panel
$panelContainer.Size = New-Object System.Drawing.Size(600, 580)
$panelContainer.Location = New-Object System.Drawing.Point(0, 0)
$panelContainer.BackColor = $BgDark
$form.Controls.Add($panelContainer)

# ---------- WELCOME PANEL (Step 0) ----------
$welcomePanel = New-Object System.Windows.Forms.Panel
$welcomePanel.Size = New-Object System.Drawing.Size(600, 580)
$welcomePanel.Location = New-Object System.Drawing.Point(0, 0)
$welcomePanel.BackColor = $BgDark
$panelContainer.Controls.Add($welcomePanel)

# Logo
$logoPanel = New-Object System.Windows.Forms.Panel
$logoPanel.Size = New-Object System.Drawing.Size(100, 100)
$logoPanel.Location = New-Object System.Drawing.Point(250, 60)
$logoPanel.BackColor = [System.Drawing.Color]::Transparent
$welcomePanel.Controls.Add($logoPanel)

$logoPanel.Add_Paint({
    param($sender, $e)
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Point(0, 0)),
        (New-Object System.Drawing.Point(100, 100)),
        $Accent,
        [System.Drawing.Color]::FromArgb(168, 85, 247)
    )
    $g.FillEllipse($brush, 5, 5, 90, 90)
    $font = New-Object System.Drawing.Font("Segoe UI", 40, [System.Drawing.FontStyle]::Bold)
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center
    $g.DrawString("Y", $font, [System.Drawing.Brushes]::White, (New-Object System.Drawing.RectangleF(0, 0, 100, 100)), $sf)
})

# Welcome title
$welcomeTitle = New-Object System.Windows.Forms.Label
$welcomeTitle.Text = "Welcome to Yapper"
$welcomeTitle.Font = New-Object System.Drawing.Font("Segoe UI", 28, [System.Drawing.FontStyle]::Bold)
$welcomeTitle.ForeColor = $TextPrimary
$welcomeTitle.AutoSize = $true
$welcomeTitle.Location = New-Object System.Drawing.Point(150, 180)
$welcomePanel.Controls.Add($welcomeTitle)

# Welcome subtitle
$welcomeSubtitle = New-Object System.Windows.Forms.Label
$welcomeSubtitle.Text = "Speech-to-Text powered by AI"
$welcomeSubtitle.Font = New-Object System.Drawing.Font("Segoe UI", 12)
$welcomeSubtitle.ForeColor = $TextSecondary
$welcomeSubtitle.AutoSize = $true
$welcomeSubtitle.Location = New-Object System.Drawing.Point(195, 225)
$welcomePanel.Controls.Add($welcomeSubtitle)

# Features list
$featuresText = @"
This wizard will install Yapper on your computer.

Features included:
  •  Voice-activated recording ("Yapper start/stop")
  •  Hotkey support (F8 by default)
  •  Real-time transcription with OpenAI Whisper
  •  Translation to 40+ languages
  •  Grammar correction
  •  System tray mode

You will need an OpenAI API key to use Yapper.
Get one at: platform.openai.com/api-keys
"@

$featuresLabel = New-Object System.Windows.Forms.Label
$featuresLabel.Text = $featuresText
$featuresLabel.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$featuresLabel.ForeColor = $TextSecondary
$featuresLabel.Size = New-Object System.Drawing.Size(450, 250)
$featuresLabel.Location = New-Object System.Drawing.Point(75, 280)
$welcomePanel.Controls.Add($featuresLabel)

# ---------- OPTIONS PANEL (Step 1) ----------
$optionsPanel = New-Object System.Windows.Forms.Panel
$optionsPanel.Size = New-Object System.Drawing.Size(600, 580)
$optionsPanel.Location = New-Object System.Drawing.Point(0, 0)
$optionsPanel.BackColor = $BgDark
$optionsPanel.Visible = $false
$panelContainer.Controls.Add($optionsPanel)

# Options title
$optionsTitle = New-Object System.Windows.Forms.Label
$optionsTitle.Text = "Installation Options"
$optionsTitle.Font = New-Object System.Drawing.Font("Segoe UI", 22, [System.Drawing.FontStyle]::Bold)
$optionsTitle.ForeColor = $TextPrimary
$optionsTitle.AutoSize = $true
$optionsTitle.Location = New-Object System.Drawing.Point(50, 40)
$optionsPanel.Controls.Add($optionsTitle)

# Install location section
$locationLabel = New-Object System.Windows.Forms.Label
$locationLabel.Text = "Install Location"
$locationLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$locationLabel.ForeColor = $TextPrimary
$locationLabel.AutoSize = $true
$locationLabel.Location = New-Object System.Drawing.Point(50, 100)
$optionsPanel.Controls.Add($locationLabel)

$locationBox = New-Object System.Windows.Forms.TextBox
$locationBox.Text = $InstallDir
$locationBox.Size = New-Object System.Drawing.Size(380, 35)
$locationBox.Location = New-Object System.Drawing.Point(50, 130)
$locationBox.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$locationBox.BackColor = $BgInput
$locationBox.ForeColor = $TextPrimary
$locationBox.BorderStyle = "FixedSingle"
$optionsPanel.Controls.Add($locationBox)

$browseBtn = New-Object System.Windows.Forms.Button
$browseBtn.Text = "Browse..."
$browseBtn.Size = New-Object System.Drawing.Size(90, 30)
$browseBtn.Location = New-Object System.Drawing.Point(440, 130)
$browseBtn.FlatStyle = "Flat"
$browseBtn.FlatAppearance.BorderColor = $Border
$browseBtn.BackColor = $BgCard
$browseBtn.ForeColor = $TextSecondary
$browseBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$optionsPanel.Controls.Add($browseBtn)

$browseBtn.Add_Click({
    $folderBrowser = New-Object System.Windows.Forms.FolderBrowserDialog
    $folderBrowser.Description = "Select installation folder"
    $folderBrowser.SelectedPath = $locationBox.Text
    if ($folderBrowser.ShowDialog() -eq "OK") {
        $locationBox.Text = $folderBrowser.SelectedPath
        $script:InstallPath = $folderBrowser.SelectedPath
    }
})

# Shortcuts section
$shortcutsLabel = New-Object System.Windows.Forms.Label
$shortcutsLabel.Text = "Shortcuts"
$shortcutsLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$shortcutsLabel.ForeColor = $TextPrimary
$shortcutsLabel.AutoSize = $true
$shortcutsLabel.Location = New-Object System.Drawing.Point(50, 200)
$optionsPanel.Controls.Add($shortcutsLabel)

# Desktop shortcut checkbox
$desktopCheck = New-Object System.Windows.Forms.CheckBox
$desktopCheck.Text = "  Create Desktop shortcut"
$desktopCheck.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$desktopCheck.ForeColor = $TextSecondary
$desktopCheck.Size = New-Object System.Drawing.Size(300, 30)
$desktopCheck.Location = New-Object System.Drawing.Point(50, 235)
$desktopCheck.Checked = $true
$desktopCheck.FlatStyle = "Flat"
$optionsPanel.Controls.Add($desktopCheck)

# Startup section
$startupLabel = New-Object System.Windows.Forms.Label
$startupLabel.Text = "Startup"
$startupLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$startupLabel.ForeColor = $TextPrimary
$startupLabel.AutoSize = $true
$startupLabel.Location = New-Object System.Drawing.Point(50, 300)
$optionsPanel.Controls.Add($startupLabel)

# Start with Windows checkbox
$startupCheck = New-Object System.Windows.Forms.CheckBox
$startupCheck.Text = "  Start Yapper with Windows (system tray)"
$startupCheck.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$startupCheck.ForeColor = $TextSecondary
$startupCheck.Size = New-Object System.Drawing.Size(350, 30)
$startupCheck.Location = New-Object System.Drawing.Point(50, 335)
$startupCheck.Checked = $false
$startupCheck.FlatStyle = "Flat"
$optionsPanel.Controls.Add($startupCheck)

$startupNote = New-Object System.Windows.Forms.Label
$startupNote.Text = "Yapper will run in the system tray when Windows starts.`nSay 'Yapper start' or press F8 to begin recording."
$startupNote.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$startupNote.ForeColor = $TextMuted
$startupNote.Size = New-Object System.Drawing.Size(400, 40)
$startupNote.Location = New-Object System.Drawing.Point(50, 370)
$optionsPanel.Controls.Add($startupNote)

# ---------- INSTALL PANEL (Step 2) ----------
$installPanel = New-Object System.Windows.Forms.Panel
$installPanel.Size = New-Object System.Drawing.Size(600, 580)
$installPanel.Location = New-Object System.Drawing.Point(0, 0)
$installPanel.BackColor = $BgDark
$installPanel.Visible = $false
$panelContainer.Controls.Add($installPanel)

# Install title
$installTitle = New-Object System.Windows.Forms.Label
$installTitle.Text = "Installing Yapper"
$installTitle.Font = New-Object System.Drawing.Font("Segoe UI", 22, [System.Drawing.FontStyle]::Bold)
$installTitle.ForeColor = $TextPrimary
$installTitle.AutoSize = $true
$installTitle.Location = New-Object System.Drawing.Point(50, 40)
$installPanel.Controls.Add($installTitle)

# Status label
$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = "Preparing installation..."
$statusLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12)
$statusLabel.ForeColor = $TextSecondary
$statusLabel.AutoSize = $true
$statusLabel.Location = New-Object System.Drawing.Point(50, 85)
$installPanel.Controls.Add($statusLabel)

# Progress bar background
$progressBg = New-Object System.Windows.Forms.Panel
$progressBg.Size = New-Object System.Drawing.Size(500, 8)
$progressBg.Location = New-Object System.Drawing.Point(50, 130)
$progressBg.BackColor = $BgCard
$installPanel.Controls.Add($progressBg)

# Progress bar fill
$progressFill = New-Object System.Windows.Forms.Panel
$progressFill.Size = New-Object System.Drawing.Size(0, 8)
$progressFill.Location = New-Object System.Drawing.Point(0, 0)
$progressFill.BackColor = $Accent
$progressBg.Controls.Add($progressFill)

# Detail label
$detailLabel = New-Object System.Windows.Forms.Label
$detailLabel.Text = ""
$detailLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$detailLabel.ForeColor = $TextMuted
$detailLabel.AutoSize = $true
$detailLabel.Location = New-Object System.Drawing.Point(50, 150)
$installPanel.Controls.Add($detailLabel)

# Log textbox
$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true
$logBox.ScrollBars = "Vertical"
$logBox.ReadOnly = $true
$logBox.Size = New-Object System.Drawing.Size(500, 300)
$logBox.Location = New-Object System.Drawing.Point(50, 190)
$logBox.BackColor = [System.Drawing.Color]::FromArgb(9, 9, 11)
$logBox.ForeColor = $TextSecondary
$logBox.BorderStyle = "FixedSingle"
$logBox.Font = New-Object System.Drawing.Font("Consolas", 9)
$installPanel.Controls.Add($logBox)

# ---------- COMPLETE PANEL (Step 3) ----------
$completePanel = New-Object System.Windows.Forms.Panel
$completePanel.Size = New-Object System.Drawing.Size(600, 580)
$completePanel.Location = New-Object System.Drawing.Point(0, 0)
$completePanel.BackColor = $BgDark
$completePanel.Visible = $false
$panelContainer.Controls.Add($completePanel)

# Success icon
$successIcon = New-Object System.Windows.Forms.Panel
$successIcon.Size = New-Object System.Drawing.Size(80, 80)
$successIcon.Location = New-Object System.Drawing.Point(260, 80)
$successIcon.BackColor = [System.Drawing.Color]::Transparent
$completePanel.Controls.Add($successIcon)

$successIcon.Add_Paint({
    param($sender, $e)
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.FillEllipse((New-Object System.Drawing.SolidBrush($Success)), 0, 0, 80, 80)
    $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::White, 5)
    $g.DrawLine($pen, 20, 40, 35, 55)
    $g.DrawLine($pen, 35, 55, 60, 25)
})

# Complete title
$completeTitle = New-Object System.Windows.Forms.Label
$completeTitle.Text = "Installation Complete!"
$completeTitle.Font = New-Object System.Drawing.Font("Segoe UI", 24, [System.Drawing.FontStyle]::Bold)
$completeTitle.ForeColor = $TextPrimary
$completeTitle.AutoSize = $true
$completeTitle.Location = New-Object System.Drawing.Point(155, 180)
$completePanel.Controls.Add($completeTitle)

# Complete message
$completeMsg = New-Object System.Windows.Forms.Label
$completeMsg.Text = "Yapper has been installed successfully."
$completeMsg.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$completeMsg.ForeColor = $TextSecondary
$completeMsg.AutoSize = $true
$completeMsg.Location = New-Object System.Drawing.Point(165, 225)
$completePanel.Controls.Add($completeMsg)

# Launch checkbox
$launchCheck = New-Object System.Windows.Forms.CheckBox
$launchCheck.Text = "  Launch Yapper now"
$launchCheck.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$launchCheck.ForeColor = $TextSecondary
$launchCheck.Size = New-Object System.Drawing.Size(250, 30)
$launchCheck.Location = New-Object System.Drawing.Point(175, 290)
$launchCheck.Checked = $true
$launchCheck.FlatStyle = "Flat"
$completePanel.Controls.Add($launchCheck)

# API key reminder
$apiReminder = New-Object System.Windows.Forms.Label
$apiReminder.Text = "Remember: You need an OpenAI API key to use Yapper.`nGet one at: platform.openai.com/api-keys"
$apiReminder.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$apiReminder.ForeColor = $TextMuted
$apiReminder.Size = New-Object System.Drawing.Size(400, 50)
$apiReminder.Location = New-Object System.Drawing.Point(110, 350)
$apiReminder.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$completePanel.Controls.Add($apiReminder)

# ============== BOTTOM BAR ==============

$bottomBar = New-Object System.Windows.Forms.Panel
$bottomBar.Size = New-Object System.Drawing.Size(600, 70)
$bottomBar.Location = New-Object System.Drawing.Point(0, 610)
$bottomBar.BackColor = $BgCard
$form.Controls.Add($bottomBar)

# Back button
$backBtn = New-Object System.Windows.Forms.Button
$backBtn.Text = "Back"
$backBtn.Size = New-Object System.Drawing.Size(100, 40)
$backBtn.Location = New-Object System.Drawing.Point(50, 15)
$backBtn.FlatStyle = "Flat"
$backBtn.FlatAppearance.BorderColor = $Border
$backBtn.BackColor = $BgDark
$backBtn.ForeColor = $TextSecondary
$backBtn.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$backBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$backBtn.Visible = $false
$bottomBar.Controls.Add($backBtn)

# Next/Install button
$nextBtn = New-Object System.Windows.Forms.Button
$nextBtn.Text = "Next"
$nextBtn.Size = New-Object System.Drawing.Size(120, 40)
$nextBtn.Location = New-Object System.Drawing.Point(330, 15)
$nextBtn.FlatStyle = "Flat"
$nextBtn.FlatAppearance.BorderSize = 0
$nextBtn.BackColor = $Accent
$nextBtn.ForeColor = $TextPrimary
$nextBtn.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$nextBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$bottomBar.Controls.Add($nextBtn)

# Cancel button
$cancelBtn = New-Object System.Windows.Forms.Button
$cancelBtn.Text = "Cancel"
$cancelBtn.Size = New-Object System.Drawing.Size(100, 40)
$cancelBtn.Location = New-Object System.Drawing.Point(460, 15)
$cancelBtn.FlatStyle = "Flat"
$cancelBtn.FlatAppearance.BorderColor = $Border
$cancelBtn.BackColor = $BgDark
$cancelBtn.ForeColor = $TextSecondary
$cancelBtn.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$cancelBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$bottomBar.Controls.Add($cancelBtn)

# ============== FUNCTIONS ==============

function Write-Log {
    param([string]$Message, [string]$Level = "info")
    $prefix = switch ($Level) {
        "success" { "[OK] " }
        "error" { "[ERR] " }
        default { "> " }
    }
    $logBox.AppendText("$prefix$Message`r`n")
    $logBox.SelectionStart = $logBox.TextLength
    $logBox.ScrollToCaret()
    [System.Windows.Forms.Application]::DoEvents()
}

function Update-Progress {
    param([int]$Percent, [string]$Status = "", [string]$Detail = "")
    $progressFill.Width = [int](($Percent / 100) * 500)
    if ($Status) { $statusLabel.Text = $Status }
    if ($Detail) { $detailLabel.Text = $Detail }
    [System.Windows.Forms.Application]::DoEvents()
}

function Show-Step {
    param([int]$Step)
    $script:CurrentStep = $Step
    $welcomePanel.Visible = ($Step -eq 0)
    $optionsPanel.Visible = ($Step -eq 1)
    $installPanel.Visible = ($Step -eq 2)
    $completePanel.Visible = ($Step -eq 3)

    $backBtn.Visible = ($Step -eq 1)

    switch ($Step) {
        0 { $nextBtn.Text = "Next" }
        1 { $nextBtn.Text = "Install" }
        2 { $nextBtn.Visible = $false; $cancelBtn.Visible = $false; $backBtn.Visible = $false }
        3 { $nextBtn.Text = "Finish"; $nextBtn.Visible = $true; $cancelBtn.Visible = $false }
    }
}

function Start-Installation {
    $script:InstallPath = $locationBox.Text
    $script:CreateDesktopShortcut = $desktopCheck.Checked
    $script:StartWithWindows = $startupCheck.Checked

    Show-Step 2

    try {
        # Step 1: Create directory
        Update-Progress 5 "Creating directories..." "Preparing installation folder"
        Write-Log "Creating installation directory..."

        if (Test-Path $script:InstallPath) { Remove-Item $script:InstallPath -Recurse -Force -ErrorAction SilentlyContinue }
        New-Item -ItemType Directory -Path $script:InstallPath -Force | Out-Null
        $PythonDir = Join-Path $script:InstallPath "python"
        New-Item -ItemType Directory -Path $PythonDir -Force | Out-Null

        Write-Log "Directory created: $($script:InstallPath)" "success"
        Update-Progress 10

        # Step 2: Download Python
        Update-Progress 10 "Downloading Python..." "Python $PythonVersion (this may take a moment)"
        Write-Log "Downloading Python $PythonVersion..."

        $pythonZip = Join-Path $script:InstallPath "python.zip"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($PythonUrl, $pythonZip)

        Write-Log "Python downloaded" "success"
        Update-Progress 30

        # Step 3: Extract Python
        Update-Progress 30 "Extracting Python..." "Unpacking files"
        Write-Log "Extracting Python..."

        Expand-Archive -Path $pythonZip -DestinationPath $PythonDir -Force
        Remove-Item $pythonZip

        $pthFile = Join-Path $PythonDir "python311._pth"
        if (Test-Path $pthFile) {
            Set-Content -Path $pthFile -Value "python311.zip`n.`nLib\site-packages`nimport site"
        }

        Write-Log "Python extracted" "success"
        Update-Progress 40

        # Step 4: Install pip
        Update-Progress 40 "Installing pip..." "Setting up package manager"
        Write-Log "Installing pip..."

        $getPip = Join-Path $script:InstallPath "get-pip.py"
        $webClient.DownloadFile($GetPipUrl, $getPip)

        $pythonExe = Join-Path $PythonDir "python.exe"
        & $pythonExe $getPip --no-warn-script-location 2>&1 | Out-Null
        Remove-Item $getPip

        Write-Log "Pip installed" "success"
        Update-Progress 50

        # Step 5: Install packages
        $totalPkgs = $Packages.Count
        $pkgNum = 0
        foreach ($pkg in $Packages) {
            $pkgNum++
            $pct = 50 + [int](($pkgNum / $totalPkgs) * 25)
            Update-Progress $pct "Installing packages..." $pkg.Display
            Write-Log "Installing $($pkg.Display)..."

            & $pythonExe -m pip install $pkg.Name -q --no-warn-script-location 2>&1 | Out-Null

            Write-Log "$($pkg.Display) installed" "success"
        }
        Update-Progress 75

        # Step 6: Copy application files
        Update-Progress 75 "Copying application..." "Installing Yapper files"
        Write-Log "Copying application files..."

        $appSrc = Join-Path $ScriptDir "app"
        $appDst = Join-Path $script:InstallPath "app"
        Copy-Item -Path $appSrc -Destination $appDst -Recurse -Force

        Get-ChildItem -Path $appDst -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
        $settingsJson = Join-Path $appDst "settings.json"
        if (Test-Path $settingsJson) { Remove-Item $settingsJson -ErrorAction SilentlyContinue }

        foreach ($file in @("yapper.ico", "yapper_icon.png", "README.md")) {
            $src = Join-Path $ScriptDir $file
            if (Test-Path $src) { Copy-Item $src -Destination $script:InstallPath -Force }
        }

        New-Item -ItemType Directory -Path (Join-Path $script:InstallPath "logs") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:InstallPath "sounds") -Force | Out-Null

        Write-Log "Application files installed" "success"
        Update-Progress 85

        # Step 7: Create launchers
        Update-Progress 85 "Creating shortcuts..." "Setting up launchers"
        Write-Log "Creating launcher scripts..."

        # Main launcher
        $yapperBat = Join-Path $script:InstallPath "Yapper.bat"
        Set-Content -Path $yapperBat -Value "@echo off`r`ncd /d `"%~dp0`"`r`nstart `"`" python\pythonw.exe app\yapper_tray.py"

        # Console launcher
        $consoleBat = Join-Path $script:InstallPath "Yapper Console.bat"
        Set-Content -Path $consoleBat -Value "@echo off`r`ntitle Yapper`r`ncd /d `"%~dp0`"`r`npython\python.exe app\yapper.py`r`npause"

        # Settings launcher
        $settingsBat = Join-Path $script:InstallPath "Settings.bat"
        Set-Content -Path $settingsBat -Value "@echo off`r`ncd /d `"%~dp0`"`r`nstart `"`" python\pythonw.exe app\settings_ui.py"

        Write-Log "Launchers created" "success"
        Update-Progress 90

        # Step 8: Create shortcuts
        if ($script:CreateDesktopShortcut) {
            Write-Log "Creating desktop shortcut..."
            $WshShell = New-Object -ComObject WScript.Shell
            $shortcut = $WshShell.CreateShortcut((Join-Path $DesktopPath "Yapper.lnk"))
            $shortcut.TargetPath = $yapperBat
            $shortcut.WorkingDirectory = $script:InstallPath
            $shortcut.IconLocation = (Join-Path $script:InstallPath "yapper.ico")
            $shortcut.Description = "Yapper - Speech to Text"
            $shortcut.Save()
            Write-Log "Desktop shortcut created" "success"
        }

        if ($script:StartWithWindows) {
            Write-Log "Adding to Windows startup..."
            $WshShell = New-Object -ComObject WScript.Shell
            $shortcut = $WshShell.CreateShortcut((Join-Path $StartupPath "Yapper.lnk"))
            $shortcut.TargetPath = $yapperBat
            $shortcut.WorkingDirectory = $script:InstallPath
            $shortcut.IconLocation = (Join-Path $script:InstallPath "yapper.ico")
            $shortcut.Description = "Yapper - Speech to Text"
            $shortcut.Save()
            Write-Log "Startup shortcut created" "success"
        }

        Update-Progress 100 "Installation complete!" ""
        Write-Log "========================================"
        Write-Log "Installation completed successfully!" "success"
        Write-Log "Installed to: $($script:InstallPath)"

        Start-Sleep -Milliseconds 500
        Show-Step 3

    } catch {
        Write-Log "ERROR: $($_.Exception.Message)" "error"
        $statusLabel.Text = "Installation failed"
        $statusLabel.ForeColor = [System.Drawing.Color]::FromArgb(239, 68, 68)
        $nextBtn.Text = "Close"
        $nextBtn.Visible = $true
        $script:InstallFailed = $true
    }
}

# ============== EVENT HANDLERS ==============

$script:InstallFailed = $false

$nextBtn.Add_Click({
    switch ($script:CurrentStep) {
        0 { Show-Step 1 }
        1 { Start-Installation }
        3 {
            if ($launchCheck.Checked -and -not $script:InstallFailed) {
                $yapperBat = Join-Path $script:InstallPath "Yapper.bat"
                if (Test-Path $yapperBat) {
                    Start-Process -FilePath $yapperBat -WorkingDirectory $script:InstallPath
                }
            }
            $form.Close()
        }
    }
})

$backBtn.Add_Click({
    if ($script:CurrentStep -eq 1) { Show-Step 0 }
})

$cancelBtn.Add_Click({
    $form.Close()
})

# Show initial step
Show-Step 0

# Show form
[void]$form.ShowDialog()
