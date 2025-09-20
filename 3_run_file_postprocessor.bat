@echo off
start "File Postprocessor" cmd /k "call venv\Scripts\activate && cd RAGside && echo Starting File Postprocessor... && python file_postprocessor.py && pause"