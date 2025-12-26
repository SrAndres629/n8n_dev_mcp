"""
Entrypoint - Server Launcher
Programmatically starts the n8n Architect server with Uvicorn.
"""
import sys
from pathlib import Path

# Ensure app is in path
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from app.core.config import settings


if __name__ == "__main__":
    print(f"🚀 Starting n8n Architect on http://{settings.api_host}:{settings.api_port}")
    print(f"📡 n8n endpoint: {settings.n8n_base_url}")
    print(f"🔧 Debug mode: {settings.debug}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="info"
    )
