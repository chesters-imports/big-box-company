@echo off
cd /d "%~dp0"
py -3.12 run-in-deck-host.py
if errorlevel 1 python run-in-deck-host.py
