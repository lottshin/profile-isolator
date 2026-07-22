@echo off
setlocal
set PY=D:\Dev\Python\python-3.13.3\python.exe
if not exist "%PY%" set PY=python
"%PY%" "%~dp0app\share_sessions.py" %*
