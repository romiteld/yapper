@echo off
:: Yapper Professional Installer Launcher
:: This launches a modern GUI installer using PowerShell

title Yapper Setup
cd /d "%~dp0"

:: Run the PowerShell installer with GUI
powershell -ExecutionPolicy Bypass -File "%~dp0installer\setup.ps1"
