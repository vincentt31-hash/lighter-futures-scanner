@echo off
setlocal
cd /d "%~dp0\.."

if not exist .venv\Scripts\python.exe (
    py -m venv .venv
)
call .venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r binance_futures_signal_scanner_v1\requirements.txt

uvicorn binance_futures_signal_scanner_v1.main:app --host 127.0.0.1 --port 8000 --reload
pause
