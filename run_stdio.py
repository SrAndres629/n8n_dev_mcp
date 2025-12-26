"""
Stdio Entrypoint - For MCP Client Integration (Antigravity/Claude)
Runs the FastMCP server in stdio mode for direct LLM integration.
"""
import sys
import os
from pathlib import Path

# Change to script directory and ensure app is in path
script_dir = Path(__file__).parent.resolve()
os.chdir(script_dir)
sys.path.insert(0, str(script_dir))

from app.main import mcp

if __name__ == "__main__":
    # Run in stdio mode for MCP client integration
    # We must suppress the startup banner that FastMCP prints to stdout
    import contextlib
    import io
    
    # Simple hack: Capture stdout during initialization if the library is chatty
    # However, FastMCP needs stdout for communication.
    # If the banner is unavoidable, we might need a different entry point.
    
    # Trying clean run
    try:
        mcp.run() 
    except KeyboardInterrupt:
        pass
