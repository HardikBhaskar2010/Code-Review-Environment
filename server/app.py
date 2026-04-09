"""
server/app.py — Compatibility wrapper
======================================
This file exists for multi-mode deployment compatibility.
The actual server code is in the root-level app.py file.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import app from root-level app.py
from app import app

__all__ = ["app", "main"]


def main():
    """Main entry point for running the server."""
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=False)


if __name__ == "__main__":
    main()
