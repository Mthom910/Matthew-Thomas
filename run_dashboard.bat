@echo off
echo Starting Insyte Dashboard...
echo.
echo Once ready, your browser will open automatically at http://localhost:8501
echo Press Ctrl+C in this window to stop the dashboard.
echo.
cd /d "%~dp0"
python -m streamlit run dashboard.py --server.headless false
pause
