@echo off
echo RAG System Starting...
echo.

cd /d "%~dp0"

echo Step 1: Check Python
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python not found!
    pause
    exit /b 1
)
echo OK

echo Step 2: Activate venv
call "%~dp0venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: venv not found, creating...
    python -m venv "%~dp0venv"
    call "%~dp0venv\Scripts\activate.bat"
)
echo OK

echo Step 3: Init DB
python -m backend.db.init_db
echo OK

echo Step 4: Gen test data
python scripts\seed_data.py
echo OK

echo Step 5: Start Backend
start "Backend" cmd /k "cd /d %~dp0 && venv\Scripts\activate.bat && uvicorn backend.main:app --host 0.0.0.0 --port 8000"

echo Step 6: Start Frontend
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo Login:    admin / 123456
echo.
echo Done! Close this window if services are running.
pause
