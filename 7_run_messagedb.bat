@echo off
start "message db" cmd /k "call venv\Scripts\activate && cd RAGside && echo Starting message db... && python messagedb.py && pause"