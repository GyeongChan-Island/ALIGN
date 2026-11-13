@echo off
cd /d "%~dp0"
py live_predict.py --port COM13
if errorlevel 1 pause
