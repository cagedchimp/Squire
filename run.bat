@echo off
cd /d "%~dp0"
if not exist .venv (
    echo Creating virtual environment and installing dependencies...
    python -m venv .venv
    .venv\Scripts\pip install -r requirements.txt
)
start "" http://127.0.0.1:8321
.venv\Scripts\python run.py
