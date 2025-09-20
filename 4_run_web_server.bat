@echo off
start "Web Server" cmd /k "call venv\Scripts\activate && cd RAGside && echo Starting Web Server... && python web_server.py && pause"