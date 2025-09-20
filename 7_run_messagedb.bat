@echo off
echo ==========================================
echo MessageDB 서버 시작
echo ==========================================
echo.
echo MessageDB 서버를 시작합니다...
echo - ZMQ 포트: 5560
echo - Flask 포트: 5001
echo.

cd /d "%~dp0RAGside"
python messagedb.py

pause