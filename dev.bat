@echo off
rem -- Start backend in a new cmd window, activating virtualenv if present
start "Backend" cmd /k "cd /d %~dp0 && (if exist ".venv\Scripts\activate.bat" (call ".venv\Scripts\activate.bat") else if exist "venv\Scripts\activate.bat" (call "venv\Scripts\activate.bat") else echo No virtual environment found. Running system Python.) && uvicorn backend.main:app --reload --port 8000"

rem -- Start frontend in a new cmd window
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
