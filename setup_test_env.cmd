@echo off
REM Script to create and setup test environment on Windows

echo Setting up test environment...

REM Create virtual environment
python -m venv test_env

REM Activate virtual environment and install requirements
call test_env\Scripts\activate.bat && pip install -r requirements-test.txt

echo Test environment setup complete!
echo To activate: test_env\Scripts\activate.bat