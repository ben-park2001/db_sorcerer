@echo off
start "Message DB Service" cmd /k "call venv\Scripts\activate && cd RAGside && echo Starting Message DB Service... && python messagedb.py && pause"