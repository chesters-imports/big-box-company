@echo off
cd /d "%~dp0box_sys"
start "" "http://127.0.0.1:42960/"
py -3.12 server.py
if errorlevel 1 python server.py
