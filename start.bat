@echo off
title Monitor de Precos Amazon
echo ====================================================
echo      INICIANDO MONITOR DE PRECOS AMAZON
echo ====================================================
echo.

echo Iniciando o Backend (FastAPI)...
start "Backend - Monitor Amazon" cmd /k "call conda activate monitor-amazon && python -m uvicorn backend.app.main:app --reload"

echo Iniciando o Frontend (Vite + React)...
start "Frontend - Monitor Amazon" cmd /k "cd frontend && npm run dev"

echo.
echo ====================================================
echo Servidores iniciados!
echo Backend: http://127.0.0.1:8000
echo Frontend: http://localhost:5173
echo ====================================================
pause
