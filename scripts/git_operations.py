#!/usr/bin/env python3
import subprocess
import sys

def run_git_command(command):
    try:
        result = subprocess.run(['git'] + command, capture_output=True, text=True, check=True)
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python git_script.py <command> [args...]")
        sys.exit(1)

    cmd = sys.argv[1:]
    run_git_command(cmd)