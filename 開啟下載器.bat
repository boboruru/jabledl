@echo off
cd /d "%~dp0"
python -c "import m3u8" 2>nul || python -m pip install m3u8 requests beautifulsoup4 pycryptodome tqdm
python gui.py
pause
