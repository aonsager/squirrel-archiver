import subprocess
import sys
import os

# Path to the file containing the lines to process
file_path = "import.txt"

# Path to the virtual environment's Python interpreter
venv_python = "venv/bin/python"

# Path to the target script to call
target_script = "squirrel.py"

if not os.path.isfile(file_path):
    print(f"Error: File '{file_path}' not found.")
    sys.exit(1)

try:
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            url, date_string = line.split(maxsplit=1)
            if line:  # Skip empty lines
                print(f"Processing: {line}")
                subprocess.run([venv_python, target_script, url, date_string], check=True)
except Exception as e:
    print(f"An error occurred: {e}")
