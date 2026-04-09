"""
server.py — Entry point for running the FastAPI server
======================================================
Simple wrapper that imports and runs the FastAPI app.
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server.app import app, main

if __name__ == "__main__":
    main()
