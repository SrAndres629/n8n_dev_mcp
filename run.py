"""
Entrypoint - Server Launcher
Silent Mode for MCP Compatibility
"""
import sys
from pathlib import Path
import uvicorn
from app.core.config import settings

# Ensure app is in path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    # 🔇 MODO SILENCIO ABSOLUTO: Sin prints, sin logs de info.
    # Esto es vital para que Antigravity no reciba basura en el canal.
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        log_level="critical", # Solo errores fatales
        access_log=False      # Desactiva logs de acceso HTTP
    )
