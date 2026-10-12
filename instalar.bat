@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Medicoes DWG x MQ - Instalacao
cd /d "%~dp0"
echo ============================================================
echo   Medicoes DWG x Mapa de Quantidades - Instalacao
echo ============================================================
echo.

rem --- 0. Este ficheiro tem de estar na pasta da aplicacao ------
if not exist "%~dp0app.py" goto :buscar_app
if not exist "%~dp0requirements.txt" goto :buscar_app

rem --- 1. Python ------------------------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY goto :sem_python
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 goto :sem_python
for /f "delims=" %%v in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set "PYVER=%%v"
echo [OK] Python !PYVER! encontrado.

rem --- 2. Ambiente virtual e bibliotecas ------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [..] A criar o ambiente da aplicacao ^(.venv^)...
    %PY% -m venv .venv
    if errorlevel 1 goto :erro
)
echo [..] A instalar as bibliotecas ^(pode demorar alguns minutos^)...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :erro
echo [OK] Bibliotecas instaladas.

rem --- 3. Evitar a pergunta de e-mail do Streamlit no 1.o arranque
if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

rem --- 4. Pasta do registo de projetistas -----------------------
if not exist "perfis" mkdir "perfis"

rem --- 5. ODA File Converter (leitura de DWG) -------------------
set "ODA="
for /d %%d in ("%ProgramFiles%\ODA\ODAFileConverter*") do if exist "%%d\ODAFileConverter.exe" set "ODA=%%d"
for /d %%d in ("%ProgramFiles(x86)%\ODA\ODAFileConverter*") do if exist "%%d\ODAFileConverter.exe" set "ODA=%%d"
if defined ODA (
    echo [OK] ODA File Converter encontrado: !ODA!
) else (
    echo.
    echo [AVISO] ODA File Converter NAO encontrado.
    echo      Sem ele a aplicacao so le ficheiros DXF.
    echo      Vai abrir a pagina de download: instale a versao Windows e
    echo      volte a executar este instalador ^(opcional^).
    start "" "https://www.opendesign.com/guestfiles/oda_file_converter"
)

rem --- 6. Atalho no ambiente de trabalho ------------------------
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Medicoes DWG x MQ.lnk');" ^
  "$s.TargetPath='%~dp0iniciar.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%SystemRoot%\System32\imageres.dll,109'; $s.Save()" >nul 2>&1
if errorlevel 1 (
    echo [AVISO] Nao foi possivel criar o atalho; use o ficheiro iniciar.bat.
) else (
    echo [OK] Atalho "Medicoes DWG x MQ" criado no ambiente de trabalho.
)

echo.
echo ============================================================
echo   Instalacao concluida. Para usar: atalho no ambiente de
echo   trabalho ou duplo clique em iniciar.bat
echo ============================================================
pause
exit /b 0

:buscar_app
set "DEST=%USERPROFILE%\Medicoes"
set "ZIP=%TEMP%\medicoes_app.zip"
set "TMPX=%TEMP%\medicoes_app"
echo [AVISO] Este instalar.bat nao esta dentro da pasta da aplicacao
echo         ^(falta o app.py ou o requirements.txt nesta pasta^).
echo.
echo [..] A descarregar a aplicacao do GitHub para:
echo      %DEST%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
  "Invoke-WebRequest -UseBasicParsing 'https://codeload.github.com/pgcconstrucoeslda/Pedro/zip/refs/heads/claude/medicoes-dwg-mq' -OutFile '%ZIP%';" ^
  "if (Test-Path '%TMPX%') { Remove-Item -Recurse -Force '%TMPX%' };" ^
  "Expand-Archive -Force '%ZIP%' '%TMPX%';" ^
  "$src = (Get-ChildItem '%TMPX%' -Directory | Select-Object -First 1).FullName;" ^
  "New-Item -ItemType Directory -Force '%DEST%' | Out-Null;" ^
  "Copy-Item -Recurse -Force (Join-Path $src '*') '%DEST%'"
if errorlevel 1 goto :sem_download
if not exist "%DEST%\instalar.bat" goto :sem_download
echo [OK] Aplicacao descarregada. A continuar a instalacao a partir de %DEST%
echo.
call "%DEST%\instalar.bat"
exit /b %errorlevel%

:sem_download
echo.
echo [ERRO] Nao foi possivel descarregar a aplicacao automaticamente.
echo        Faca manualmente: GitHub ^> pgcconstrucoeslda/Pedro ^> ramo claude/medicoes-dwg-mq
echo        ^> Code ^> Download ZIP. Descompacte e execute o instalar.bat DENTRO dessa pasta.
start "" "https://github.com/pgcconstrucoeslda/Pedro/tree/claude/medicoes-dwg-mq"
pause
exit /b 1

:sem_python
echo [AVISO] Python 3.10 ou superior nao encontrado.
echo      Vai abrir a pagina de download do Python.
echo      Na instalacao marque a opcao "Add python.exe to PATH"
echo      e depois volte a executar este instalador.
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1

:erro
echo.
echo [ERRO] A instalacao falhou. Verifique a ligacao a internet e tente de novo.
echo        Se o erro persistir, envie uma fotografia desta janela.
pause
exit /b 1
