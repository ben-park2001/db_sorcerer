@echo off
start "Chroma DB Server" cmd /k "call venv\Scripts\activate && cd RAGside && echo Starting Chroma DB Server... && chroma run --host localhost --port 8000"