@echo off
start "File Preprocessor" cmd /k "call venv\Scripts\activate && cd RAGside && echo Starting File Preprocessor... && python file_preprocessor.py && pause"