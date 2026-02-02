@echo off
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0installer\settings_gui.ps1"
