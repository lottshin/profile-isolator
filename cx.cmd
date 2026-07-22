@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0cx.ps1" %*
exit /b %ERRORLEVEL%
