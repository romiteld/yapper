# Yapper Professional Installer
# Modern GUI installer using Windows Forms
# Copyright (c) 2026 Cloudelipute

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Configuration
$PythonVersion = "3.11.9"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
$GetPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$ScriptDir = Split-Path -Parent $PSScriptRoot
$BuildDir = Join-Path $ScriptDir "build"
$DistDir = Join-Path $ScriptDir "dist"

$Packages = @(
    @{Name="openai"; Display="OpenAI API Client"},
    @{Name="keyboard"; Display="Keyboard Hotkeys"},
    @{Name="pyaudio"; Display="Audio Recording"},
    @{Name="pystray"; Display="System Tray"},
    @{Name="Pillow"; Display="Image Processing"},
    @{Name="customtkinter"; Display="Modern UI"}
)

# Colors
$BgDark = [System.Drawing.Color]::FromArgb(10, 10, 15)
$BgCard = [System.Drawing.Color]::FromArgb(18, 18, 26)
$Accent = [System.Drawing.Color]::FromArgb(99, 102, 241)
$AccentHover = [System.Drawing.Color]::FromArgb(129, 140, 248)
$TextPrimary = [System.Drawing.Color]::White
$TextSecondary = [System.Drawing.Color]::FromArgb(161, 161, 170)
$Success = [System.Drawing.Color]::FromArgb(34, 197, 94)
$ErrorColor = [System.Drawing.Color]::FromArgb(239, 68, 68)

# Create main form
$form = New-Object System.Windows.Forms.Form
$form.Text = "Yapper Installer"
$form.Size = New-Object System.Drawing.Size(550, 650)
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

# Logo placeholder (circle with Y)
$logoPanel = New-Object System.Windows.Forms.Panel
$logoPanel.Size = New-Object System.Drawing.Size(80, 80)
$logoPanel.Location = New-Object System.Drawing.Point(235, 30)
$logoPanel.BackColor = [System.Drawing.Color]::Transparent
$form.Controls.Add($logoPanel)

$logoPanel.Add_Paint({
    param($sender, $e)
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

    # Draw gradient circle
    $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Point(0, 0)),
        (New-Object System.Drawing.Point(80, 80)),
        $Accent,
        [System.Drawing.Color]::FromArgb(168, 85, 247)
    )
    $g.FillEllipse($brush, 0, 0, 78, 78)

    # Draw Y
    $font = New-Object System.Drawing.Font("Segoe UI", 32, [System.Drawing.FontStyle]::Bold)
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center
    $g.DrawString("Y", $font, [System.Drawing.Brushes]::White, (New-Object System.Drawing.RectangleF(0, 0, 80, 80)), $sf)
})

# Title
$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = "Yapper"
$titleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 36, [System.Drawing.FontStyle]::Bold)
$titleLabel.ForeColor = $TextPrimary
$titleLabel.AutoSize = $true
$titleLabel.Location = New-Object System.Drawing.Point(200, 120)
$form.Controls.Add($titleLabel)

# Subtitle
$subtitleLabel = New-Object System.Windows.Forms.Label
$subtitleLabel.Text = "Speech-to-Text • Powered by AI"
$subtitleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$subtitleLabel.ForeColor = $TextSecondary
$subtitleLabel.AutoSize = $true
$subtitleLabel.Location = New-Object System.Drawing.Point(175, 175)
$form.Controls.Add($subtitleLabel)

# Progress card panel
$progressPanel = New-Object System.Windows.Forms.Panel
$progressPanel.Size = New-Object System.Drawing.Size(470, 120)
$progressPanel.Location = New-Object System.Drawing.Point(40, 220)
$progressPanel.BackColor = $BgCard
$form.Controls.Add($progressPanel)

# Round corners for panel (draw event)
$progressPanel.Add_Paint({
    param($sender, $e)
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $rect = New-Object System.Drawing.Rectangle(0, 0, $sender.Width - 1, $sender.Height - 1)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $radius = 16
    $path.AddArc($rect.X, $rect.Y, $radius, $radius, 180, 90)
    $path.AddArc($rect.Right - $radius, $rect.Y, $radius, $radius, 270, 90)
    $path.AddArc($rect.Right - $radius, $rect.Bottom - $radius, $radius, $radius, 0, 90)
    $path.AddArc($rect.X, $rect.Bottom - $radius, $radius, $radius, 90, 90)
    $path.CloseFigure()
    $sender.Region = New-Object System.Drawing.Region($path)
})

# Status label
$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = "Ready to install"
$statusLabel.Font = New-Object System.Drawing.Font("Segoe UI", 13, [System.Drawing.FontStyle]::Bold)
$statusLabel.ForeColor = $TextPrimary
$statusLabel.AutoSize = $true
$statusLabel.Location = New-Object System.Drawing.Point(20, 20)
$progressPanel.Controls.Add($statusLabel)

# Progress bar
$progressBar = New-Object System.Windows.Forms.ProgressBar
$progressBar.Size = New-Object System.Drawing.Size(430, 10)
$progressBar.Location = New-Object System.Drawing.Point(20, 55)
$progressBar.Style = "Continuous"
$progressBar.Value = 0
$progressPanel.Controls.Add($progressBar)

# Detail label
$detailLabel = New-Object System.Windows.Forms.Label
$detailLabel.Text = "Click Install to begin"
$detailLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$detailLabel.ForeColor = $TextSecondary
$detailLabel.AutoSize = $true
$detailLabel.Location = New-Object System.Drawing.Point(20, 80)
$progressPanel.Controls.Add($detailLabel)

# Log panel
$logPanel = New-Object System.Windows.Forms.Panel
$logPanel.Size = New-Object System.Drawing.Size(470, 220)
$logPanel.Location = New-Object System.Drawing.Point(40, 355)
$logPanel.BackColor = $BgCard
$form.Controls.Add($logPanel)

$logPanel.Add_Paint({
    param($sender, $e)
    $rect = New-Object System.Drawing.Rectangle(0, 0, $sender.Width - 1, $sender.Height - 1)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $radius = 16
    $path.AddArc($rect.X, $rect.Y, $radius, $radius, 180, 90)
    $path.AddArc($rect.Right - $radius, $rect.Y, $radius, $radius, 270, 90)
    $path.AddArc($rect.Right - $radius, $rect.Bottom - $radius, $radius, $radius, 0, 90)
    $path.AddArc($rect.X, $rect.Bottom - $radius, $radius, $radius, 90, 90)
    $path.CloseFigure()
    $sender.Region = New-Object System.Drawing.Region($path)
})

# Log header
$logHeader = New-Object System.Windows.Forms.Label
$logHeader.Text = "Installation Log"
$logHeader.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$logHeader.ForeColor = $TextSecondary
$logHeader.AutoSize = $true
$logHeader.Location = New-Object System.Drawing.Point(15, 12)
$logPanel.Controls.Add($logHeader)

# Log textbox
$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true
$logBox.ScrollBars = "Vertical"
$logBox.ReadOnly = $true
$logBox.Size = New-Object System.Drawing.Size(440, 165)
$logBox.Location = New-Object System.Drawing.Point(15, 40)
$logBox.BackColor = [System.Drawing.Color]::FromArgb(9, 9, 11)
$logBox.ForeColor = $TextSecondary
$logBox.BorderStyle = "None"
$logBox.Font = New-Object System.Drawing.Font("Consolas", 9)
$logPanel.Controls.Add($logBox)

# Install button
$installBtn = New-Object System.Windows.Forms.Button
$installBtn.Text = "Install"
$installBtn.Size = New-Object System.Drawing.Size(220, 45)
$installBtn.Location = New-Object System.Drawing.Point(40, 590)
$installBtn.FlatStyle = "Flat"
$installBtn.FlatAppearance.BorderSize = 0
$installBtn.BackColor = $Accent
$installBtn.ForeColor = $TextPrimary
$installBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$installBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$form.Controls.Add($installBtn)

# Cancel button
$cancelBtn = New-Object System.Windows.Forms.Button
$cancelBtn.Text = "Cancel"
$cancelBtn.Size = New-Object System.Drawing.Size(220, 45)
$cancelBtn.Location = New-Object System.Drawing.Point(290, 590)
$cancelBtn.FlatStyle = "Flat"
$cancelBtn.FlatAppearance.BorderSize = 0
$cancelBtn.BackColor = [System.Drawing.Color]::FromArgb(39, 39, 42)
$cancelBtn.ForeColor = $TextSecondary
$cancelBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12)
$cancelBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$form.Controls.Add($cancelBtn)

# Helper functions
function Write-Log {
    param([string]$Message, [string]$Level = "info")

    $prefix = switch ($Level) {
        "success" { "[OK] " }
        "error" { "[ERR] " }
        "warning" { "[!] " }
        default { "> " }
    }

    $logBox.AppendText("$prefix$Message`r`n")
    $logBox.SelectionStart = $logBox.TextLength
    $logBox.ScrollToCaret()
    [System.Windows.Forms.Application]::DoEvents()
}

function Update-Status {
    param([string]$Status, [string]$Detail = "")
    $statusLabel.Text = $Status
    if ($Detail) { $detailLabel.Text = $Detail }
    [System.Windows.Forms.Application]::DoEvents()
}

function Update-Progress {
    param([int]$Value)
    $progressBar.Value = [Math]::Min(100, [Math]::Max(0, $Value))
    [System.Windows.Forms.Application]::DoEvents()
}

# Install function
function Start-Installation {
    $installBtn.Enabled = $false
    $installBtn.Text = "Installing..."

    try {
        # Step 1: Prepare
        Update-Status "Preparing..." "Setting up directories"
        Update-Progress 5
        Write-Log "Preparing build directory"

        if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
        New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
        $PythonDir = Join-Path $BuildDir "python"
        New-Item -ItemType Directory -Path $PythonDir -Force | Out-Null

        Write-Log "Build directory ready" "success"
        Update-Progress 10

        # Step 2: Download Python
        Update-Status "Downloading Python" "Python $PythonVersion embeddable"
        Write-Log "Downloading Python $PythonVersion..."

        $pythonZip = Join-Path $BuildDir "python.zip"
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($PythonUrl, $pythonZip)

        Write-Log "Python downloaded" "success"
        Update-Progress 30

        # Step 3: Extract Python
        Update-Status "Extracting Python" "Unpacking files..."
        Write-Log "Extracting Python..."

        Expand-Archive -Path $pythonZip -DestinationPath $PythonDir -Force
        Remove-Item $pythonZip

        # Configure for pip
        $pthFile = Join-Path $PythonDir "python311._pth"
        if (Test-Path $pthFile) {
            Set-Content -Path $pthFile -Value "python311.zip`n.`nLib\site-packages`nimport site"
        }

        Write-Log "Python extracted" "success"
        Update-Progress 40

        # Step 4: Install pip
        Update-Status "Installing pip" "Package manager setup"
        Write-Log "Installing pip..."

        $getPip = Join-Path $BuildDir "get-pip.py"
        $webClient.DownloadFile($GetPipUrl, $getPip)

        $pythonExe = Join-Path $PythonDir "python.exe"
        & $pythonExe $getPip --no-warn-script-location 2>&1 | Out-Null
        Remove-Item $getPip

        Write-Log "Pip installed" "success"
        Update-Progress 50

        # Step 5: Install packages
        $totalPackages = $Packages.Count
        $currentPackage = 0

        foreach ($pkg in $Packages) {
            $currentPackage++
            Update-Status "Installing packages" $pkg.Display
            Write-Log "Installing $($pkg.Display)..."

            & $pythonExe -m pip install $pkg.Name -q --no-warn-script-location 2>&1 | Out-Null

            $progress = 50 + (($currentPackage / $totalPackages) * 30)
            Update-Progress $progress
            Write-Log "$($pkg.Display) installed" "success"
        }

        # Step 6: Copy app files
        Update-Status "Finalizing" "Copying application files"
        Write-Log "Copying application files..."

        $appSrc = Join-Path $ScriptDir "app"
        $appDst = Join-Path $BuildDir "app"
        Copy-Item -Path $appSrc -Destination $appDst -Recurse

        # Remove __pycache__ and settings.json
        Get-ChildItem -Path $appDst -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
        $settingsFile = Join-Path $appDst "settings.json"
        if (Test-Path $settingsFile) { Remove-Item $settingsFile }

        # Copy assets
        foreach ($file in @("yapper.ico", "yapper_icon.png", "README.md")) {
            $src = Join-Path $ScriptDir $file
            if (Test-Path $src) {
                Copy-Item $src -Destination $BuildDir
            }
        }

        # Create directories
        New-Item -ItemType Directory -Path (Join-Path $BuildDir "logs") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $BuildDir "sounds") -Force | Out-Null

        # Create launchers
        Set-Content -Path (Join-Path $BuildDir "Yapper.bat") -Value '@echo off`r`ncd /d "%~dp0"`r`nstart "" python\pythonw.exe app\yapper_tray.py'
        Set-Content -Path (Join-Path $BuildDir "Yapper Console.bat") -Value '@echo off`r`ntitle Yapper`r`ncd /d "%~dp0"`r`npython\python.exe app\yapper.py`r`npause'
        Set-Content -Path (Join-Path $BuildDir "Settings.bat") -Value '@echo off`r`ncd /d "%~dp0"`r`nstart "" python\pythonw.exe app\settings_ui.py'
        Set-Content -Path (Join-Path $BuildDir "First Run.bat") -Value '@echo off`r`ntitle Yapper Setup`r`ncd /d "%~dp0"`r`necho.`r`necho   Welcome to Yapper!`r`necho.`r`necho   Get your API key at: https://platform.openai.com/api-keys`r`necho.`r`npython\python.exe app\settings_console.py`r`npause'

        Write-Log "Application files copied" "success"
        Update-Progress 90

        # Create distribution zip
        Update-Status "Creating package" "Building distribution..."
        Write-Log "Creating distribution package..."

        if (-not (Test-Path $DistDir)) { New-Item -ItemType Directory -Path $DistDir -Force | Out-Null }

        $zipPath = Join-Path $DistDir "Yapper-Portable-Windows.zip"
        if (Test-Path $zipPath) { Remove-Item $zipPath }

        Compress-Archive -Path "$BuildDir\*" -DestinationPath $zipPath -Force

        $sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
        Write-Log "Package created ($sizeMB MB)" "success"
        Update-Progress 100

        # Success
        Update-Status "Installation Complete!" "Yapper is ready to use"
        $statusLabel.ForeColor = $Success
        Write-Log "========================================"
        Write-Log "Installation completed successfully!" "success"
        Write-Log "Output: $zipPath"

        $installBtn.Text = "Open Folder"
        $installBtn.BackColor = $Success
        $installBtn.Enabled = $true
        $cancelBtn.Text = "Close"

        $script:InstallComplete = $true

    } catch {
        Update-Status "Installation Failed" $_.Exception.Message.Substring(0, [Math]::Min(50, $_.Exception.Message.Length))
        $statusLabel.ForeColor = $ErrorColor
        Write-Log "Error: $($_.Exception.Message)" "error"

        $installBtn.Text = "Retry"
        $installBtn.Enabled = $true
        $cancelBtn.Text = "Close"
    }
}

# Event handlers
$script:InstallComplete = $false

$installBtn.Add_Click({
    if ($script:InstallComplete) {
        Start-Process explorer.exe -ArgumentList $DistDir
    } else {
        Start-Installation
    }
})

$cancelBtn.Add_Click({
    $form.Close()
})

# Show form
[void]$form.ShowDialog()
