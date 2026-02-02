# Yapper Professional Installer
# Modern GUI installer with setup options
# Copyright (c) 2026 Cloudelipute

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

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

# Colors - Pink Theme (matching icon)
$BgDark = [System.Drawing.Color]::FromArgb(18, 18, 24)
$BgCard = [System.Drawing.Color]::FromArgb(28, 28, 36)
$BgInput = [System.Drawing.Color]::FromArgb(38, 38, 48)
$Pink = [System.Drawing.Color]::FromArgb(236, 72, 153)
$PinkLight = [System.Drawing.Color]::FromArgb(244, 114, 182)
$PinkDark = [System.Drawing.Color]::FromArgb(219, 39, 119)
$TextPrimary = [System.Drawing.Color]::White
$TextSecondary = [System.Drawing.Color]::FromArgb(180, 180, 190)
$TextMuted = [System.Drawing.Color]::FromArgb(120, 120, 130)
$Success = [System.Drawing.Color]::FromArgb(34, 197, 94)
$Border = [System.Drawing.Color]::FromArgb(50, 50, 60)

# State
$script:CurrentStep = 0
$script:CreateDesktopShortcut = $true
$script:StartWithWindows = $false
$script:InstallPath = $InstallDir
$script:ApiKey = ""

# Create main form
$form = New-Object System.Windows.Forms.Form
$form.Text = "Yapper Setup"
$form.Size = New-Object System.Drawing.Size(650, 750)
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

# ============== HELPER FUNCTION ==============

function New-CenteredLabel {
    param(
        [string]$Text,
        [int]$Y,
        [int]$FontSize = 10,
        [System.Drawing.FontStyle]$FontStyle = [System.Drawing.FontStyle]::Regular,
        [System.Drawing.Color]$Color = $TextSecondary,
        [System.Windows.Forms.Control]$Parent,
        [int]$Width = 600
    )
    $label = New-Object System.Windows.Forms.Label
    $label.Text = $Text
    $label.Font = New-Object System.Drawing.Font("Segoe UI", $FontSize, $FontStyle)
    $label.ForeColor = $Color
    $label.Size = New-Object System.Drawing.Size($Width, ([int]($FontSize * 2.5)))
    $label.Location = New-Object System.Drawing.Point(([int]((650 - $Width) / 2)), $Y)
    $label.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
    $Parent.Controls.Add($label)
    return $label
}

# ============== STEP PANELS ==============

# Create panel container
$panelContainer = New-Object System.Windows.Forms.Panel
$panelContainer.Size = New-Object System.Drawing.Size(650, 620)
$panelContainer.Location = New-Object System.Drawing.Point(0, 0)
$panelContainer.BackColor = $BgDark
$form.Controls.Add($panelContainer)

# ---------- WELCOME PANEL (Step 0) ----------
$welcomePanel = New-Object System.Windows.Forms.Panel
$welcomePanel.Size = New-Object System.Drawing.Size(650, 620)
$welcomePanel.Location = New-Object System.Drawing.Point(0, 0)
$welcomePanel.BackColor = $BgDark
$panelContainer.Controls.Add($welcomePanel)

# Logo - Pink circle with Y
$logoPanel = New-Object System.Windows.Forms.Panel
$logoPanel.Size = New-Object System.Drawing.Size(100, 100)
$logoPanel.Location = New-Object System.Drawing.Point(275, 50)
$logoPanel.BackColor = [System.Drawing.Color]::Transparent
$welcomePanel.Controls.Add($logoPanel)

$logoPanel.Add_Paint({
    param($sender, $e)
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $brush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        (New-Object System.Drawing.Point(0, 0)),
        (New-Object System.Drawing.Point(100, 100)),
        $Pink,
        $PinkDark
    )
    $g.FillEllipse($brush, 5, 5, 90, 90)
    $font = New-Object System.Drawing.Font("Segoe UI", 42, [System.Drawing.FontStyle]::Bold)
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center
    $g.DrawString("Y", $font, [System.Drawing.Brushes]::White, (New-Object System.Drawing.RectangleF(0, 0, 100, 100)), $sf)
})

# Welcome title - centered
$welcomeTitle = New-CenteredLabel -Text "Welcome to Yapper" -Y 170 -FontSize 28 -FontStyle Bold -Color $TextPrimary -Parent $welcomePanel

# Welcome subtitle - centered
$welcomeSubtitle = New-CenteredLabel -Text "Speech-to-Text powered by AI" -Y 220 -FontSize 13 -Color $TextSecondary -Parent $welcomePanel

# Divider
$divider = New-Object System.Windows.Forms.Panel
$divider.Size = New-Object System.Drawing.Size(400, 1)
$divider.Location = New-Object System.Drawing.Point(125, 260)
$divider.BackColor = $Border
$welcomePanel.Controls.Add($divider)

# Features title
$featuresTitle = New-CenteredLabel -Text "This wizard will install Yapper on your computer" -Y 280 -FontSize 11 -Color $TextSecondary -Parent $welcomePanel

# Features list (centered)
$features = @(
    "Voice-activated recording - say 'Yapper start/stop'",
    "Hotkey support (F8 by default)",
    "Real-time transcription with OpenAI Whisper",
    "Translation to 40+ languages",
    "Automatic grammar correction",
    "Runs quietly in system tray"
)

$featureY = 330
foreach ($feature in $features) {
    $featureLabel = New-Object System.Windows.Forms.Label
    $featureLabel.Text = [char]0x2022 + "  " + $feature
    $featureLabel.Font = New-Object System.Drawing.Font("Segoe UI", 10)
    $featureLabel.ForeColor = $TextSecondary
    $featureLabel.Size = New-Object System.Drawing.Size(450, 28)
    $featureLabel.Location = New-Object System.Drawing.Point(100, $featureY)
    $welcomePanel.Controls.Add($featureLabel)
    $featureY += 28
}

# API key note
$apiNote = New-CenteredLabel -Text "You will need an OpenAI API key to use Yapper" -Y 530 -FontSize 10 -Color $TextMuted -Parent $welcomePanel

$apiLink = New-Object System.Windows.Forms.LinkLabel
$apiLink.Text = "Get one at platform.openai.com/api-keys"
$apiLink.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$apiLink.LinkColor = $PinkLight
$apiLink.ActiveLinkColor = $Pink
$apiLink.Size = New-Object System.Drawing.Size(300, 25)
$apiLink.Location = New-Object System.Drawing.Point(175, 555)
$apiLink.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$apiLink.Add_LinkClicked({ Start-Process "https://platform.openai.com/api-keys" })
$welcomePanel.Controls.Add($apiLink)

# ---------- API KEY PANEL (Step 1) ----------
$apiPanel = New-Object System.Windows.Forms.Panel
$apiPanel.Size = New-Object System.Drawing.Size(650, 620)
$apiPanel.Location = New-Object System.Drawing.Point(0, 0)
$apiPanel.BackColor = $BgDark
$apiPanel.Visible = $false
$panelContainer.Controls.Add($apiPanel)

# API Key icon
$keyIcon = New-Object System.Windows.Forms.Panel
$keyIcon.Size = New-Object System.Drawing.Size(80, 80)
$keyIcon.Location = New-Object System.Drawing.Point(285, 50)
$keyIcon.BackColor = [System.Drawing.Color]::Transparent
$apiPanel.Controls.Add($keyIcon)

$keyIcon.Add_Paint({
    param($sender, $e)
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.FillEllipse((New-Object System.Drawing.SolidBrush($BgCard)), 0, 0, 80, 80)
    $pen = New-Object System.Drawing.Pen($Pink, 3)
    # Draw key shape
    $g.DrawEllipse($pen, 20, 25, 25, 25)
    $g.DrawLine($pen, 45, 38, 65, 38)
    $g.DrawLine($pen, 55, 38, 55, 48)
    $g.DrawLine($pen, 62, 38, 62, 45)
})

# API title
$apiTitle = New-CenteredLabel -Text "Enter Your API Key" -Y 150 -FontSize 24 -FontStyle Bold -Color $TextPrimary -Parent $apiPanel

# API description
$apiDesc = New-CenteredLabel -Text "Yapper uses OpenAI's Whisper for transcription." -Y 200 -FontSize 11 -Color $TextSecondary -Parent $apiPanel
$apiDesc2 = New-CenteredLabel -Text "Enter your API key below to enable speech-to-text." -Y 225 -FontSize 11 -Color $TextSecondary -Parent $apiPanel

# API Key label
$apiKeyLabel = New-Object System.Windows.Forms.Label
$apiKeyLabel.Text = "OpenAI API Key"
$apiKeyLabel.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$apiKeyLabel.ForeColor = $TextPrimary
$apiKeyLabel.Size = New-Object System.Drawing.Size(150, 25)
$apiKeyLabel.Location = New-Object System.Drawing.Point(100, 290)
$apiPanel.Controls.Add($apiKeyLabel)

# API Key textbox
$apiKeyBox = New-Object System.Windows.Forms.TextBox
$apiKeyBox.Size = New-Object System.Drawing.Size(450, 40)
$apiKeyBox.Location = New-Object System.Drawing.Point(100, 320)
$apiKeyBox.Font = New-Object System.Drawing.Font("Consolas", 11)
$apiKeyBox.BackColor = $BgInput
$apiKeyBox.ForeColor = $TextPrimary
$apiKeyBox.BorderStyle = "FixedSingle"
$apiKeyBox.Text = ""
$apiPanel.Controls.Add($apiKeyBox)

# Placeholder text behavior
$apiKeyBox.Add_GotFocus({
    if ($apiKeyBox.Text -eq "sk-...") {
        $apiKeyBox.Text = ""
        $apiKeyBox.ForeColor = $TextPrimary
    }
})

# API Key hint
$apiKeyHint = New-Object System.Windows.Forms.Label
$apiKeyHint.Text = "Starts with 'sk-' - Your key is stored locally and never shared"
$apiKeyHint.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$apiKeyHint.ForeColor = $TextMuted
$apiKeyHint.Size = New-Object System.Drawing.Size(450, 20)
$apiKeyHint.Location = New-Object System.Drawing.Point(100, 365)
$apiPanel.Controls.Add($apiKeyHint)

# Get API key link
$getKeyLink = New-Object System.Windows.Forms.LinkLabel
$getKeyLink.Text = "Don't have an API key? Get one here"
$getKeyLink.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$getKeyLink.LinkColor = $PinkLight
$getKeyLink.ActiveLinkColor = $Pink
$getKeyLink.Size = New-Object System.Drawing.Size(300, 25)
$getKeyLink.Location = New-Object System.Drawing.Point(175, 420)
$getKeyLink.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$getKeyLink.Add_LinkClicked({ Start-Process "https://platform.openai.com/api-keys" })
$apiPanel.Controls.Add($getKeyLink)

# Skip note
$skipNote = New-CenteredLabel -Text "You can also set this later in Settings" -Y 480 -FontSize 10 -Color $TextMuted -Parent $apiPanel

# ---------- OPTIONS PANEL (Step 2) ----------
$optionsPanel = New-Object System.Windows.Forms.Panel
$optionsPanel.Size = New-Object System.Drawing.Size(650, 620)
$optionsPanel.Location = New-Object System.Drawing.Point(0, 0)
$optionsPanel.BackColor = $BgDark
$optionsPanel.Visible = $false
$panelContainer.Controls.Add($optionsPanel)

# Options title
$optionsTitle = New-CenteredLabel -Text "Installation Options" -Y 40 -FontSize 24 -FontStyle Bold -Color $TextPrimary -Parent $optionsPanel

# Install location section
$locationLabel = New-Object System.Windows.Forms.Label
$locationLabel.Text = "Install Location"
$locationLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$locationLabel.ForeColor = $TextPrimary
$locationLabel.Size = New-Object System.Drawing.Size(200, 30)
$locationLabel.Location = New-Object System.Drawing.Point(100, 110)
$optionsPanel.Controls.Add($locationLabel)

$locationBox = New-Object System.Windows.Forms.TextBox
$locationBox.Text = $InstallDir
$locationBox.Size = New-Object System.Drawing.Size(340, 35)
$locationBox.Location = New-Object System.Drawing.Point(100, 145)
$locationBox.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$locationBox.BackColor = $BgInput
$locationBox.ForeColor = $TextPrimary
$locationBox.BorderStyle = "FixedSingle"
$optionsPanel.Controls.Add($locationBox)

$browseBtn = New-Object System.Windows.Forms.Button
$browseBtn.Text = "Browse..."
$browseBtn.Size = New-Object System.Drawing.Size(90, 32)
$browseBtn.Location = New-Object System.Drawing.Point(450, 145)
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
$shortcutsLabel.Size = New-Object System.Drawing.Size(200, 30)
$shortcutsLabel.Location = New-Object System.Drawing.Point(100, 220)
$optionsPanel.Controls.Add($shortcutsLabel)

# Desktop shortcut checkbox
$desktopCheck = New-Object System.Windows.Forms.CheckBox
$desktopCheck.Text = "  Create Desktop shortcut"
$desktopCheck.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$desktopCheck.ForeColor = $TextSecondary
$desktopCheck.Size = New-Object System.Drawing.Size(350, 30)
$desktopCheck.Location = New-Object System.Drawing.Point(100, 255)
$desktopCheck.Checked = $true
$desktopCheck.FlatStyle = "Flat"
$optionsPanel.Controls.Add($desktopCheck)

# Startup section
$startupLabel = New-Object System.Windows.Forms.Label
$startupLabel.Text = "Startup"
$startupLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$startupLabel.ForeColor = $TextPrimary
$startupLabel.Size = New-Object System.Drawing.Size(200, 30)
$startupLabel.Location = New-Object System.Drawing.Point(100, 320)
$optionsPanel.Controls.Add($startupLabel)

# Start with Windows checkbox
$startupCheck = New-Object System.Windows.Forms.CheckBox
$startupCheck.Text = "  Start Yapper with Windows (system tray)"
$startupCheck.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$startupCheck.ForeColor = $TextSecondary
$startupCheck.Size = New-Object System.Drawing.Size(400, 30)
$startupCheck.Location = New-Object System.Drawing.Point(100, 355)
$startupCheck.Checked = $false
$startupCheck.FlatStyle = "Flat"
$optionsPanel.Controls.Add($startupCheck)

$startupNote = New-Object System.Windows.Forms.Label
$startupNote.Text = "Yapper will run in the system tray when Windows starts.`nSay 'Yapper start' or press F8 to begin recording."
$startupNote.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$startupNote.ForeColor = $TextMuted
$startupNote.Size = New-Object System.Drawing.Size(400, 45)
$startupNote.Location = New-Object System.Drawing.Point(100, 390)
$optionsPanel.Controls.Add($startupNote)

# ---------- INSTALL PANEL (Step 3) ----------
$installPanel = New-Object System.Windows.Forms.Panel
$installPanel.Size = New-Object System.Drawing.Size(650, 620)
$installPanel.Location = New-Object System.Drawing.Point(0, 0)
$installPanel.BackColor = $BgDark
$installPanel.Visible = $false
$panelContainer.Controls.Add($installPanel)

# Install title
$installTitle = New-CenteredLabel -Text "Installing Yapper" -Y 40 -FontSize 24 -FontStyle Bold -Color $TextPrimary -Parent $installPanel

# Status label
$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = "Preparing installation..."
$statusLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12)
$statusLabel.ForeColor = $TextSecondary
$statusLabel.Size = New-Object System.Drawing.Size(500, 30)
$statusLabel.Location = New-Object System.Drawing.Point(75, 90)
$statusLabel.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$installPanel.Controls.Add($statusLabel)

# Progress bar background
$progressBg = New-Object System.Windows.Forms.Panel
$progressBg.Size = New-Object System.Drawing.Size(500, 10)
$progressBg.Location = New-Object System.Drawing.Point(75, 135)
$progressBg.BackColor = $BgCard
$installPanel.Controls.Add($progressBg)

# Progress bar fill
$progressFill = New-Object System.Windows.Forms.Panel
$progressFill.Size = New-Object System.Drawing.Size(0, 10)
$progressFill.Location = New-Object System.Drawing.Point(0, 0)
$progressFill.BackColor = $Pink
$progressBg.Controls.Add($progressFill)

# Detail label
$detailLabel = New-Object System.Windows.Forms.Label
$detailLabel.Text = ""
$detailLabel.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$detailLabel.ForeColor = $TextMuted
$detailLabel.Size = New-Object System.Drawing.Size(500, 25)
$detailLabel.Location = New-Object System.Drawing.Point(75, 155)
$detailLabel.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
$installPanel.Controls.Add($detailLabel)

# Log textbox
$logBox = New-Object System.Windows.Forms.TextBox
$logBox.Multiline = $true
$logBox.ScrollBars = "Vertical"
$logBox.ReadOnly = $true
$logBox.Size = New-Object System.Drawing.Size(500, 350)
$logBox.Location = New-Object System.Drawing.Point(75, 195)
$logBox.BackColor = [System.Drawing.Color]::FromArgb(12, 12, 16)
$logBox.ForeColor = $TextSecondary
$logBox.BorderStyle = "FixedSingle"
$logBox.Font = New-Object System.Drawing.Font("Consolas", 9)
$installPanel.Controls.Add($logBox)

# ---------- COMPLETE PANEL (Step 4) ----------
$completePanel = New-Object System.Windows.Forms.Panel
$completePanel.Size = New-Object System.Drawing.Size(650, 620)
$completePanel.Location = New-Object System.Drawing.Point(0, 0)
$completePanel.BackColor = $BgDark
$completePanel.Visible = $false
$panelContainer.Controls.Add($completePanel)

# Success icon
$successIcon = New-Object System.Windows.Forms.Panel
$successIcon.Size = New-Object System.Drawing.Size(100, 100)
$successIcon.Location = New-Object System.Drawing.Point(275, 80)
$successIcon.BackColor = [System.Drawing.Color]::Transparent
$completePanel.Controls.Add($successIcon)

$successIcon.Add_Paint({
    param($sender, $e)
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.FillEllipse((New-Object System.Drawing.SolidBrush($Success)), 10, 10, 80, 80)
    $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::White, 6)
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $g.DrawLine($pen, 30, 50, 45, 65)
    $g.DrawLine($pen, 45, 65, 72, 35)
})

# Complete title
$completeTitle = New-CenteredLabel -Text "Installation Complete!" -Y 200 -FontSize 26 -FontStyle Bold -Color $TextPrimary -Parent $completePanel

# Complete message
$completeMsg = New-CenteredLabel -Text "Yapper has been installed successfully." -Y 250 -FontSize 12 -Color $TextSecondary -Parent $completePanel

# Launch checkbox (centered)
$launchCheck = New-Object System.Windows.Forms.CheckBox
$launchCheck.Text = "  Launch Yapper now"
$launchCheck.Font = New-Object System.Drawing.Font("Segoe UI", 12)
$launchCheck.ForeColor = $TextSecondary
$launchCheck.Size = New-Object System.Drawing.Size(220, 35)
$launchCheck.Location = New-Object System.Drawing.Point(215, 320)
$launchCheck.Checked = $true
$launchCheck.FlatStyle = "Flat"
$completePanel.Controls.Add($launchCheck)

# Divider
$completeDivider = New-Object System.Windows.Forms.Panel
$completeDivider.Size = New-Object System.Drawing.Size(400, 1)
$completeDivider.Location = New-Object System.Drawing.Point(125, 390)
$completeDivider.BackColor = $Border
$completePanel.Controls.Add($completeDivider)

# Quick start tips
$tipsTitle = New-CenteredLabel -Text "Quick Start" -Y 415 -FontSize 12 -FontStyle Bold -Color $TextPrimary -Parent $completePanel

$tip1 = New-CenteredLabel -Text "Say 'Yapper start' to begin recording" -Y 450 -FontSize 10 -Color $TextSecondary -Parent $completePanel
$tip2 = New-CenteredLabel -Text "Say 'Yapper stop' to transcribe" -Y 475 -FontSize 10 -Color $TextSecondary -Parent $completePanel
$tip3 = New-CenteredLabel -Text "Or press F8 to toggle recording" -Y 500 -FontSize 10 -Color $TextSecondary -Parent $completePanel

# ============== BOTTOM BAR ==============

$bottomBar = New-Object System.Windows.Forms.Panel
$bottomBar.Size = New-Object System.Drawing.Size(650, 80)
$bottomBar.Location = New-Object System.Drawing.Point(0, 650)
$bottomBar.BackColor = $BgCard
$form.Controls.Add($bottomBar)

# Back button
$backBtn = New-Object System.Windows.Forms.Button
$backBtn.Text = "Back"
$backBtn.Size = New-Object System.Drawing.Size(100, 42)
$backBtn.Location = New-Object System.Drawing.Point(50, 18)
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
$nextBtn.Size = New-Object System.Drawing.Size(130, 42)
$nextBtn.Location = New-Object System.Drawing.Point(360, 18)
$nextBtn.FlatStyle = "Flat"
$nextBtn.FlatAppearance.BorderSize = 0
$nextBtn.BackColor = $Pink
$nextBtn.ForeColor = $TextPrimary
$nextBtn.Font = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)
$nextBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$bottomBar.Controls.Add($nextBtn)

# Cancel button
$cancelBtn = New-Object System.Windows.Forms.Button
$cancelBtn.Text = "Cancel"
$cancelBtn.Size = New-Object System.Drawing.Size(100, 42)
$cancelBtn.Location = New-Object System.Drawing.Point(500, 18)
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
    $apiPanel.Visible = ($Step -eq 1)
    $optionsPanel.Visible = ($Step -eq 2)
    $installPanel.Visible = ($Step -eq 3)
    $completePanel.Visible = ($Step -eq 4)

    $backBtn.Visible = ($Step -ge 1 -and $Step -le 2)

    switch ($Step) {
        0 { $nextBtn.Text = "Get Started" }
        1 { $nextBtn.Text = "Next" }
        2 { $nextBtn.Text = "Install" }
        3 { $nextBtn.Visible = $false; $cancelBtn.Visible = $false; $backBtn.Visible = $false }
        4 { $nextBtn.Text = "Finish"; $nextBtn.Visible = $true; $cancelBtn.Visible = $false }
    }
}

function Start-Installation {
    $script:InstallPath = $locationBox.Text
    $script:CreateDesktopShortcut = $desktopCheck.Checked
    $script:StartWithWindows = $startupCheck.Checked
    $script:ApiKey = $apiKeyBox.Text.Trim()

    Show-Step 3

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

        foreach ($file in @("yapper.ico", "yapper_icon.png", "README.md")) {
            $src = Join-Path $ScriptDir $file
            if (Test-Path $src) { Copy-Item $src -Destination $script:InstallPath -Force }
        }

        New-Item -ItemType Directory -Path (Join-Path $script:InstallPath "logs") -Force | Out-Null
        New-Item -ItemType Directory -Path (Join-Path $script:InstallPath "sounds") -Force | Out-Null

        Write-Log "Application files installed" "success"
        Update-Progress 80

        # Step 7: Save API key if provided
        if ($script:ApiKey -and $script:ApiKey.StartsWith("sk-")) {
            Write-Log "Saving API key..."
            $settingsPath = Join-Path $appDst "settings.json"
            $settings = @{
                api_key = $script:ApiKey
                hotkey = "f8"
                translate_to = ""
                fix_grammar = $true
                vad_enabled = $true
            }
            $settings | ConvertTo-Json | Set-Content -Path $settingsPath
            Write-Log "API key saved" "success"
        }
        Update-Progress 85

        # Step 8: Create launchers
        Update-Progress 85 "Creating shortcuts..." "Setting up launchers"
        Write-Log "Creating launcher scripts..."

        # Main launcher
        $yapperBat = Join-Path $script:InstallPath "Yapper.bat"
        Set-Content -Path $yapperBat -Value "@echo off`r`ncd /d `"%~dp0`"`r`nstart `"`" python\pythonw.exe app\yapper_tray.py"

        # Console launcher
        $consoleBat = Join-Path $script:InstallPath "Yapper Console.bat"
        Set-Content -Path $consoleBat -Value "@echo off`r`ntitle Yapper`r`ncd /d `"%~dp0`"`r`npython\python.exe app\yapper.py`r`npause"

        # Settings launcher (UI, not CLI!)
        $settingsBat = Join-Path $script:InstallPath "Settings.bat"
        Set-Content -Path $settingsBat -Value "@echo off`r`ncd /d `"%~dp0`"`r`nstart `"`" python\pythonw.exe app\settings_ui.py"

        Write-Log "Launchers created" "success"
        Update-Progress 90

        # Step 9: Create shortcuts
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
        Show-Step 4

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
        1 { Show-Step 2 }
        2 { Start-Installation }
        4 {
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
    elseif ($script:CurrentStep -eq 2) { Show-Step 1 }
})

$cancelBtn.Add_Click({
    $form.Close()
})

# Show initial step
Show-Step 0

# Show form
[void]$form.ShowDialog()
