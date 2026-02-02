# Yapper Settings GUI
# PowerShell Windows Forms settings interface
# Copyright (c) 2026 Cloudelipute

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()

# Get script directory (installed location)
$AppDir = Split-Path -Parent $PSScriptRoot
if ($PSScriptRoot -eq "") { $AppDir = $PWD }
$SettingsFile = Join-Path $AppDir "app\settings.json"

# Colors - Pink Theme
$BgDark = [System.Drawing.Color]::FromArgb(18, 18, 24)
$BgCard = [System.Drawing.Color]::FromArgb(28, 28, 36)
$BgInput = [System.Drawing.Color]::FromArgb(38, 38, 48)
$Pink = [System.Drawing.Color]::FromArgb(236, 72, 153)
$PinkLight = [System.Drawing.Color]::FromArgb(244, 114, 182)
$TextPrimary = [System.Drawing.Color]::White
$TextSecondary = [System.Drawing.Color]::FromArgb(180, 180, 190)
$TextMuted = [System.Drawing.Color]::FromArgb(120, 120, 130)
$Border = [System.Drawing.Color]::FromArgb(50, 50, 60)
$Success = [System.Drawing.Color]::FromArgb(34, 197, 94)

# Hotkey options
$HotkeyOptions = @("f8", "f9", "f10", "f11", "f12", "pause", "scroll lock", "insert")

# Language options
$Languages = [ordered]@{
    "" = "No Translation"
    "en" = "English"
    "es" = "Spanish"
    "fr" = "French"
    "de" = "German"
    "it" = "Italian"
    "pt" = "Portuguese"
    "nl" = "Dutch"
    "pl" = "Polish"
    "ru" = "Russian"
    "ja" = "Japanese"
    "ko" = "Korean"
    "zh" = "Chinese"
    "ar" = "Arabic"
    "hi" = "Hindi"
}

# Load settings
function Load-Settings {
    $defaults = @{
        api_key = ""
        hotkey = "f8"
        translate_to = ""
        fix_grammar = $true
        vad_enabled = $true
        vad_threshold_db = -45
        audio_feedback = $true
        always_listening = $true
        wake_word_fuzzy = $true
    }

    if (Test-Path $SettingsFile) {
        try {
            $loaded = Get-Content $SettingsFile -Raw | ConvertFrom-Json
            foreach ($key in $defaults.Keys) {
                if ($null -ne $loaded.$key) {
                    $defaults[$key] = $loaded.$key
                }
            }
        } catch {}
    }
    return $defaults
}

# Save settings
function Save-Settings {
    param($Settings)
    try {
        $dir = Split-Path $SettingsFile
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $Settings | ConvertTo-Json | Set-Content -Path $SettingsFile
        return $true
    } catch {
        return $false
    }
}

$script:Settings = Load-Settings

# Create form
$form = New-Object System.Windows.Forms.Form
$form.Text = "Yapper Settings"
$form.Size = New-Object System.Drawing.Size(500, 700)
$form.StartPosition = "CenterScreen"
$form.FormBorderStyle = "FixedSingle"
$form.MaximizeBox = $false
$form.BackColor = $BgDark
$form.Font = New-Object System.Drawing.Font("Segoe UI", 10)

# Icon
$iconPath = Join-Path $AppDir "yapper.ico"
if (Test-Path $iconPath) {
    try { $form.Icon = New-Object System.Drawing.Icon($iconPath) } catch {}
}

# Scrollable panel
$scrollPanel = New-Object System.Windows.Forms.Panel
$scrollPanel.Size = New-Object System.Drawing.Size(480, 620)
$scrollPanel.Location = New-Object System.Drawing.Point(10, 10)
$scrollPanel.AutoScroll = $true
$scrollPanel.BackColor = $BgDark
$form.Controls.Add($scrollPanel)

$yPos = 10

# ===== HEADER =====
$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = "Yapper Settings"
$titleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 22, [System.Drawing.FontStyle]::Bold)
$titleLabel.ForeColor = $TextPrimary
$titleLabel.Size = New-Object System.Drawing.Size(400, 40)
$titleLabel.Location = New-Object System.Drawing.Point(10, $yPos)
$scrollPanel.Controls.Add($titleLabel)
$yPos += 50

# ===== API KEY SECTION =====
$apiCard = New-Object System.Windows.Forms.Panel
$apiCard.Size = New-Object System.Drawing.Size(440, 120)
$apiCard.Location = New-Object System.Drawing.Point(10, $yPos)
$apiCard.BackColor = $BgCard
$scrollPanel.Controls.Add($apiCard)

$apiLabel = New-Object System.Windows.Forms.Label
$apiLabel.Text = "OpenAI API Key"
$apiLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$apiLabel.ForeColor = $TextPrimary
$apiLabel.Location = New-Object System.Drawing.Point(15, 12)
$apiLabel.AutoSize = $true
$apiCard.Controls.Add($apiLabel)

$apiLink = New-Object System.Windows.Forms.LinkLabel
$apiLink.Text = "Get API Key"
$apiLink.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$apiLink.LinkColor = $PinkLight
$apiLink.Location = New-Object System.Drawing.Point(350, 14)
$apiLink.AutoSize = $true
$apiLink.Add_LinkClicked({ Start-Process "https://platform.openai.com/api-keys" })
$apiCard.Controls.Add($apiLink)

$apiBox = New-Object System.Windows.Forms.TextBox
$apiBox.Size = New-Object System.Drawing.Size(410, 30)
$apiBox.Location = New-Object System.Drawing.Point(15, 45)
$apiBox.Font = New-Object System.Drawing.Font("Consolas", 11)
$apiBox.BackColor = $BgInput
$apiBox.ForeColor = $TextPrimary
$apiBox.BorderStyle = "FixedSingle"
$apiBox.UseSystemPasswordChar = $true
$apiBox.Text = $script:Settings.api_key
$apiCard.Controls.Add($apiBox)

$showKeyCheck = New-Object System.Windows.Forms.CheckBox
$showKeyCheck.Text = "Show API key"
$showKeyCheck.Font = New-Object System.Drawing.Font("Segoe UI", 9)
$showKeyCheck.ForeColor = $TextMuted
$showKeyCheck.Location = New-Object System.Drawing.Point(15, 85)
$showKeyCheck.AutoSize = $true
$showKeyCheck.FlatStyle = "Flat"
$showKeyCheck.Add_CheckedChanged({
    $apiBox.UseSystemPasswordChar = -not $showKeyCheck.Checked
})
$apiCard.Controls.Add($showKeyCheck)

$yPos += 130

# ===== HOTKEY SECTION =====
$hotkeyCard = New-Object System.Windows.Forms.Panel
$hotkeyCard.Size = New-Object System.Drawing.Size(440, 90)
$hotkeyCard.Location = New-Object System.Drawing.Point(10, $yPos)
$hotkeyCard.BackColor = $BgCard
$scrollPanel.Controls.Add($hotkeyCard)

$hotkeyLabel = New-Object System.Windows.Forms.Label
$hotkeyLabel.Text = "Recording Hotkey"
$hotkeyLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$hotkeyLabel.ForeColor = $TextPrimary
$hotkeyLabel.Location = New-Object System.Drawing.Point(15, 12)
$hotkeyLabel.AutoSize = $true
$hotkeyCard.Controls.Add($hotkeyLabel)

$hotkeyCombo = New-Object System.Windows.Forms.ComboBox
$hotkeyCombo.Size = New-Object System.Drawing.Size(150, 30)
$hotkeyCombo.Location = New-Object System.Drawing.Point(15, 45)
$hotkeyCombo.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$hotkeyCombo.BackColor = $BgInput
$hotkeyCombo.ForeColor = $TextPrimary
$hotkeyCombo.FlatStyle = "Flat"
$hotkeyCombo.DropDownStyle = "DropDownList"
$hotkeyCombo.Items.AddRange($HotkeyOptions)
$hotkeyCombo.SelectedItem = $script:Settings.hotkey
$hotkeyCard.Controls.Add($hotkeyCombo)

$yPos += 100

# ===== TRANSLATION SECTION =====
$transCard = New-Object System.Windows.Forms.Panel
$transCard.Size = New-Object System.Drawing.Size(440, 90)
$transCard.Location = New-Object System.Drawing.Point(10, $yPos)
$transCard.BackColor = $BgCard
$scrollPanel.Controls.Add($transCard)

$transLabel = New-Object System.Windows.Forms.Label
$transLabel.Text = "Translation"
$transLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$transLabel.ForeColor = $TextPrimary
$transLabel.Location = New-Object System.Drawing.Point(15, 12)
$transLabel.AutoSize = $true
$transCard.Controls.Add($transLabel)

$transCombo = New-Object System.Windows.Forms.ComboBox
$transCombo.Size = New-Object System.Drawing.Size(250, 30)
$transCombo.Location = New-Object System.Drawing.Point(15, 45)
$transCombo.Font = New-Object System.Drawing.Font("Segoe UI", 11)
$transCombo.BackColor = $BgInput
$transCombo.ForeColor = $TextPrimary
$transCombo.FlatStyle = "Flat"
$transCombo.DropDownStyle = "DropDownList"
$transCombo.Items.AddRange($Languages.Values)
$currentLang = $Languages[$script:Settings.translate_to]
if ($currentLang) { $transCombo.SelectedItem = $currentLang } else { $transCombo.SelectedIndex = 0 }
$transCard.Controls.Add($transCombo)

$yPos += 100

# ===== OPTIONS SECTION =====
$optCard = New-Object System.Windows.Forms.Panel
$optCard.Size = New-Object System.Drawing.Size(440, 160)
$optCard.Location = New-Object System.Drawing.Point(10, $yPos)
$optCard.BackColor = $BgCard
$scrollPanel.Controls.Add($optCard)

$optLabel = New-Object System.Windows.Forms.Label
$optLabel.Text = "Options"
$optLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$optLabel.ForeColor = $TextPrimary
$optLabel.Location = New-Object System.Drawing.Point(15, 12)
$optLabel.AutoSize = $true
$optCard.Controls.Add($optLabel)

$grammarCheck = New-Object System.Windows.Forms.CheckBox
$grammarCheck.Text = "Grammar Correction"
$grammarCheck.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$grammarCheck.ForeColor = $TextSecondary
$grammarCheck.Location = New-Object System.Drawing.Point(15, 45)
$grammarCheck.AutoSize = $true
$grammarCheck.FlatStyle = "Flat"
$grammarCheck.Checked = $script:Settings.fix_grammar
$optCard.Controls.Add($grammarCheck)

$feedbackCheck = New-Object System.Windows.Forms.CheckBox
$feedbackCheck.Text = "Audio Feedback Sounds"
$feedbackCheck.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$feedbackCheck.ForeColor = $TextSecondary
$feedbackCheck.Location = New-Object System.Drawing.Point(15, 75)
$feedbackCheck.AutoSize = $true
$feedbackCheck.FlatStyle = "Flat"
$feedbackCheck.Checked = $script:Settings.audio_feedback
$optCard.Controls.Add($feedbackCheck)

$fuzzyCheck = New-Object System.Windows.Forms.CheckBox
$fuzzyCheck.Text = "Fuzzy Wake Word Detection"
$fuzzyCheck.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$fuzzyCheck.ForeColor = $TextSecondary
$fuzzyCheck.Location = New-Object System.Drawing.Point(15, 105)
$fuzzyCheck.AutoSize = $true
$fuzzyCheck.FlatStyle = "Flat"
$fuzzyCheck.Checked = $script:Settings.wake_word_fuzzy
$optCard.Controls.Add($fuzzyCheck)

$yPos += 170

# ===== VAD SECTION =====
$vadCard = New-Object System.Windows.Forms.Panel
$vadCard.Size = New-Object System.Drawing.Size(440, 120)
$vadCard.Location = New-Object System.Drawing.Point(10, $yPos)
$vadCard.BackColor = $BgCard
$scrollPanel.Controls.Add($vadCard)

$vadLabel = New-Object System.Windows.Forms.Label
$vadLabel.Text = "Voice Activity Detection"
$vadLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$vadLabel.ForeColor = $TextPrimary
$vadLabel.Location = New-Object System.Drawing.Point(15, 12)
$vadLabel.AutoSize = $true
$vadCard.Controls.Add($vadLabel)

$vadCheck = New-Object System.Windows.Forms.CheckBox
$vadCheck.Text = "Enabled (reduces API costs)"
$vadCheck.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$vadCheck.ForeColor = $TextSecondary
$vadCheck.Location = New-Object System.Drawing.Point(15, 45)
$vadCheck.AutoSize = $true
$vadCheck.FlatStyle = "Flat"
$vadCheck.Checked = $script:Settings.vad_enabled
$vadCard.Controls.Add($vadCheck)

$sensLabel = New-Object System.Windows.Forms.Label
$sensLabel.Text = "Sensitivity:"
$sensLabel.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$sensLabel.ForeColor = $TextSecondary
$sensLabel.Location = New-Object System.Drawing.Point(15, 80)
$sensLabel.AutoSize = $true
$vadCard.Controls.Add($sensLabel)

$vadSlider = New-Object System.Windows.Forms.TrackBar
$vadSlider.Size = New-Object System.Drawing.Size(250, 30)
$vadSlider.Location = New-Object System.Drawing.Point(100, 75)
$vadSlider.Minimum = -60
$vadSlider.Maximum = -10
$vadSlider.Value = $script:Settings.vad_threshold_db
$vadSlider.TickFrequency = 10
$vadSlider.BackColor = $BgCard
$vadCard.Controls.Add($vadSlider)

$vadValue = New-Object System.Windows.Forms.Label
$vadValue.Text = "$($script:Settings.vad_threshold_db) dB"
$vadValue.Font = New-Object System.Drawing.Font("Segoe UI", 10)
$vadValue.ForeColor = $TextSecondary
$vadValue.Location = New-Object System.Drawing.Point(360, 80)
$vadValue.AutoSize = $true
$vadCard.Controls.Add($vadValue)

$vadSlider.Add_ValueChanged({
    $vadValue.Text = "$($vadSlider.Value) dB"
})

$yPos += 130

# ===== BUTTONS =====
$saveBtn = New-Object System.Windows.Forms.Button
$saveBtn.Text = "Save Settings"
$saveBtn.Size = New-Object System.Drawing.Size(440, 45)
$saveBtn.Location = New-Object System.Drawing.Point(10, $yPos)
$saveBtn.FlatStyle = "Flat"
$saveBtn.FlatAppearance.BorderSize = 0
$saveBtn.BackColor = $Pink
$saveBtn.ForeColor = $TextPrimary
$saveBtn.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$saveBtn.Cursor = [System.Windows.Forms.Cursors]::Hand
$scrollPanel.Controls.Add($saveBtn)

$saveBtn.Add_Click({
    # Get language code from name
    $langCode = ""
    foreach ($key in $Languages.Keys) {
        if ($Languages[$key] -eq $transCombo.SelectedItem) {
            $langCode = $key
            break
        }
    }

    $newSettings = @{
        api_key = $apiBox.Text
        hotkey = $hotkeyCombo.SelectedItem
        translate_to = $langCode
        fix_grammar = $grammarCheck.Checked
        vad_enabled = $vadCheck.Checked
        vad_threshold_db = $vadSlider.Value
        audio_feedback = $feedbackCheck.Checked
        always_listening = $true
        wake_word_fuzzy = $fuzzyCheck.Checked
    }

    if (Save-Settings $newSettings) {
        [System.Windows.Forms.MessageBox]::Show("Settings saved successfully!", "Yapper", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information)
    } else {
        [System.Windows.Forms.MessageBox]::Show("Failed to save settings!", "Error", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error)
    }
})

[void]$form.ShowDialog()
