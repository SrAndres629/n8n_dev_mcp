# n8n Architect MCP Server

Production-grade MCP server for n8n workflow orchestration.

## Features

- **Smart Upsert**: Create or update workflows by name
- **Deep Diagnostics**: Analyze failed executions with detailed error extraction
- **Package Management**: Install community nodes via npm
- **Auto-Fix**: Composite tool to diagnose and patch failing workflows

## Quick Start

### Windows
```batch
start_server.bat
```

### Manual Setup
```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run server
python run.py
```

## Configuration

Create a `.env` file:
```env
N8N_API_KEY=your_api_key_here
N8N_BASE_URL=http://localhost:5678/api/v1
N8N_EDITOR_URL=http://localhost:5678
N8N_DATA_DIR=~/.n8n
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false
```

## Available Tools

| Tool | Description |
|:---|:---|
| `list_all_workflows` | List workflows with optional tag filter |
| `deploy_workflow` | Smart Upsert: create or update by name |
| `read_workflow_structure` | Get full workflow JSON |
| `diagnose_execution` | Deep dive into failed execution |
| `auto_fix_workflow` | Diagnose + patch in one call |
| `install_community_node` | Install npm packages |
| `toggle_workflow_state` | Activate/deactivate workflows |
| `delete_workflow` | Remove workflows |

## API Endpoints

- `GET /health` - Server health check
- `GET /info` - Server configuration

## Architecture

```
app/
├── core/
│   ├── config.py    # Pydantic Settings
│   ├── client.py    # HTTP Client + error handling
│   └── logging.py   # Structured logging
├── models/
│   └── schemas.py   # Data contracts
├── services/
│   ├── architect.py # Deploy/Read/Clone
│   ├── debugger.py  # Diagnostics
│   ├── manager.py   # List/Toggle/Delete
│   └── packages.py  # npm management
└── main.py          # FastAPI + FastMCP gateway
```
