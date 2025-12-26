"""
Main Application Gateway
Exposes all n8n tools via FastMCP with FastAPI integration.
"""
import json
from contextlib import asynccontextmanager
from typing import Union, List, Dict, Any, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastmcp import FastMCP

from app.core.config import settings
from app.core.client import get_client, safe_tool
from app.core.logging import gateway_logger as logger

# Import all service functions
from app.services.manager import (
    list_all_workflows,
    toggle_workflow_state,
    delete_workflow,
    get_workflow_tags
)
from app.services.architect import (
    read_workflow_structure,
    deploy_workflow,
    clone_workflow
)
from app.services.debugger import (
    diagnose_execution,
    analyze_execution_failures,
    get_execution_history
)
from app.services.packages import (
    install_community_node,
    uninstall_community_node,
    list_installed_nodes,
    get_n8n_info
)


# =============================================================================
# LIFESPAN MANAGER
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application lifecycle.
    - Startup: Log configuration
    - Shutdown: Close HTTP client
    """
    logger.info("=" * 60)
    logger.info("🚀 n8n Architect MCP Server Starting")
    logger.info(f"📡 n8n API: {settings.n8n_base_url}")
    logger.info(f"🌐 Editor: {settings.n8n_editor_url}")
    logger.info(f"📁 Data Dir: {settings.n8n_data_dir}")
    logger.info("=" * 60)
    
    yield
    
    # Cleanup
    client = get_client()
    await client.close()
    logger.info("👋 n8n Architect MCP Server Shutdown")


# =============================================================================
# FASTAPI APP INITIALIZATION
# =============================================================================
app = FastAPI(
    title="n8n Architect API",
    description="Production-grade API and MCP server for n8n workflow orchestration.",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# GLOBAL EXCEPTION HANDLER
# =============================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catches any unhandled error and returns it in Envelope format.
    Ensures n8n never receives a raw error.
    """
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "code": 500,
            "message": str(exc),
            "path": str(request.url.path)
        }
    )


# =============================================================================
# HEALTH & INFO ENDPOINTS
# =============================================================================
@app.get("/health")
async def health_check():
    """Check server and n8n connectivity status."""
    try:
        client = get_client()
        await client.get("/workflows")
        n8n_status = "connected"
    except Exception as e:
        n8n_status = f"error: {str(e)[:50]}"
    
    return {
        "status": "healthy",
        "n8n_connection": n8n_status,
        "version": "2.0.0"
    }


@app.get("/info")
async def server_info():
    """Get server configuration info."""
    return {
        "name": "n8n Architect",
        "version": "2.0.0",
        "n8n_base_url": settings.n8n_base_url,
        "n8n_editor_url": settings.n8n_editor_url,
        "n8n_data_dir": settings.n8n_data_dir
    }


# =============================================================================
# FASTMCP SERVER INITIALIZATION
# =============================================================================
mcp = FastMCP("n8n Architect")

# --- Register Management Tools ---
mcp.tool()(list_all_workflows)
mcp.tool()(toggle_workflow_state)
mcp.tool()(delete_workflow)
mcp.tool()(get_workflow_tags)

# --- Register Architecture Tools ---
mcp.tool()(read_workflow_structure)
mcp.tool()(deploy_workflow)
mcp.tool()(clone_workflow)

# --- Register Debugging Tools ---
mcp.tool()(diagnose_execution)
mcp.tool()(analyze_execution_failures)
mcp.tool()(get_execution_history)

# --- Register Package Management Tools ---
mcp.tool()(install_community_node)
mcp.tool()(uninstall_community_node)
mcp.tool()(list_installed_nodes)
mcp.tool()(get_n8n_info)


# =============================================================================
# COMPOSITE TOOLS (High-Level Operations)
# =============================================================================
@mcp.tool()
@safe_tool
async def auto_fix_workflow(
    execution_id: str,
    fixed_nodes: Union[str, List[Dict[str, Any]]],
    fixed_connections: Union[str, Dict[str, Any], None] = None
) -> str:
    """
    Auto-fix a failing workflow: diagnose the error, then apply a patch.
    
    This is a composite tool that:
    1. Reads the failed execution to get workflow ID and error details
    2. Reads the current workflow structure
    3. Applies the fixed nodes/connections
    
    Args:
        execution_id: ID of the failed execution to fix
        fixed_nodes: The corrected node definitions
        fixed_connections: Optional corrected connections (uses existing if not provided)
    
    Returns:
        JSON string with diagnosis and fix result.
    """
    logger.info(f"Auto-fix initiated for execution: {execution_id}")
    
    # Step 1: Diagnose the failure
    diagnosis_result = await diagnose_execution(execution_id)
    diagnosis = json.loads(diagnosis_result)
    
    if "error" in diagnosis.get("status", ""):
        return diagnosis_result
    
    workflow_id = diagnosis.get("workflow", {}).get("workflow_id")
    workflow_name = diagnosis.get("workflow", {}).get("workflow_name", "Unknown")
    
    if not workflow_id:
        return json.dumps({
            "status": "error",
            "message": "Could not determine workflow ID from execution"
        }, indent=2)
    
    logger.info(f"Diagnosed workflow: {workflow_name} ({workflow_id})")
    
    # Step 2: Get current workflow if connections not provided
    if fixed_connections is None:
        logger.info("Fetching current workflow connections")
        current_wf = await read_workflow_structure(workflow_id)
        current_data = json.loads(current_wf)
        fixed_connections = current_data.get("connections", {})
    
    # Step 3: Deploy the fix
    logger.info("Deploying fixed workflow")
    deploy_result = await deploy_workflow(
        name=workflow_name,
        nodes=fixed_nodes,
        connections=fixed_connections,
        activate=False  # Don't auto-activate fixed workflows
    )
    
    deploy_data = json.loads(deploy_result)
    
    result = {
        "status": "success",
        "action": "auto_fix",
        "original_error": {
            "execution_id": execution_id,
            "failed_node": diagnosis.get("diagnosis", {}).get("failed_node"),
            "error_message": diagnosis.get("diagnosis", {}).get("error_message")
        },
        "fix_result": deploy_data,
        "next_steps": "Review the fixed workflow and activate when ready."
    }
    
    logger.info(f"Auto-fix completed for workflow: {workflow_id}")
    return json.dumps(result, indent=2)


@mcp.tool()
@safe_tool
async def create_workflow(
    name: str,
    nodes_json: str,
    connections_json: str,
    activate: bool = False
) -> str:
    """
    Create a new workflow from JSON strings.
    This is an alias for deploy_workflow, designed for AI agents
    that prefer to pass JSON as strings.
    
    Args:
        name: Name for the new workflow
        nodes_json: JSON string containing node definitions
        connections_json: JSON string containing connections
        activate: Whether to activate after creation
    
    Returns:
        JSON string with creation result.
    """
    return await deploy_workflow(
        name=name,
        nodes=nodes_json,
        connections=connections_json,
        activate=activate
    )


@mcp.tool()
@safe_tool
async def install_external_node(package_name: str) -> str:
    """
    Install an external/community node from npm.
    Alias for install_community_node with clearer naming.
    
    Args:
        package_name: The npm package name (e.g., 'n8n-nodes-browserless')
    
    Returns:
        JSON string with installation result.
    """
    return await install_community_node(package_name)


def get_mcp() -> FastMCP:
    """Get the FastMCP server instance."""
    return mcp


def get_app() -> FastAPI:
    """Get the FastAPI app instance."""
    return app


if __name__ == "__main__":
    mcp.run()
