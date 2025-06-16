#!/bin/bash

# Script to create and setup test environment (WSL/Linux)
echo "Setting up test environment for WSL/Linux..."

# Use python3 for WSL compatibility
python3 -m venv test_env

# Activate virtual environment and install requirements
source test_env/bin/activate
pip install -r requirements-test.txt

echo "Test environment setup complete!"
echo "To activate: source test_env/bin/activate"