@echo off
start "Oracle Database Service" cmd /k "call venv\Scripts\activate && cd STORAGEside && echo Starting Oracle Database Service... && python oracle.py && pause"