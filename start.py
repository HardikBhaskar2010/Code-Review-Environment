#!/usr/bin/env python3
"""
start.py - Startup script with better error handling
"""
import sys
import traceback

try:
    # Try to import app module
    import app as app_module
    
    # Check if app exists
    if not hasattr(app_module, 'app'):
        print("ERROR: app module imported but 'app' attribute not found")
        print("Available attributes:", dir(app_module))
        sys.exit(1)
    
    print("✓ App module loaded successfully")
    print("✓ App attribute found")
    
    # Now start uvicorn
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7860)
    
except Exception as e:
    print(f"ERROR during startup: {e}")
    traceback.print_exc()
    sys.exit(1)
