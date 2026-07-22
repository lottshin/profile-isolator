@echo off
setlocal
start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0cx-gui.ps1"
