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
    mcp.run()
