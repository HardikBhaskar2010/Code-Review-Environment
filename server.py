"""
server.py — Entry point for running the FastAPI server
======================================================
Simple wrapper that imports and runs the FastAPI app.
"""

from server.app import app, main

if __name__ == "__main__":
    main()
