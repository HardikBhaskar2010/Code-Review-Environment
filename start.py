#!/usr/bin/env python3
"""
start.py - Startup script with better error handling
"""
import sys
import traceback

try:
    # Try to import server module
    import server
    
    # Check if app exists
    if not hasattr(server, 'app'):
        print("ERROR: server module imported but 'app' attribute not found")
        print("Available attributes:", dir(server))
        sys.exit(1)
    
    print("✓ Server module loaded successfully")
    print("✓ App attribute found")
    
    # Now start uvicorn
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=7860)
    
except Exception as e:
    print(f"ERROR during startup: {e}")
    traceback.print_exc()
    sys.exit(1)
