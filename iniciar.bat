@echo off
setlocal
title Medicoes DWG x MQ
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo A aplicacao ainda nao esta instalada. Execute primeiro o instalar.bat
    pause
    exit /b 1
)
echo A iniciar a aplicacao... o browser vai abrir em http://localhost:8501
echo Para fechar a aplicacao, feche esta janela.
echo.
set "MEDICOES_PERFIS=%~dp0perfis\projetistas.json"
".venv\Scripts\python.exe" -m streamlit run app.py
if errorlevel 1 pause
