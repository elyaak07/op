@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>&1
  if not errorlevel 1 (
    py -3 -m venv .venv || goto :error
  ) else (
    python -m venv .venv || goto :error
  )
)
if not exist ".venv\motor_op_v14_installed" (
  echo Installation des dependances Motor OP Studio V1.4...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
  echo OK>".venv\motor_op_v14_installed"
)
echo.
echo Ouverture de Motor OP Studio sur http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless false
if errorlevel 1 goto :error
goto :eof
:error
echo.
echo Une erreur est survenue. Copiez les messages affiches ci-dessus.
pause
