#!/usr/bin/env python3
import sys
from pathlib import Path

# Add the project root directory to Python path
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

if __name__ == "__main__":
    try:
        from src.cli.manage import app
        app()
    except ImportError as e:
        print(f"Error importing application: {e}")
        print("Make sure you have installed the dependencies: pip install -r requirements.txt")
        sys.exit(1)

