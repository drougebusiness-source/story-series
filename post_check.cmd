@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" post_check.py %1 >> logs\post-check-run.log 2>&1
