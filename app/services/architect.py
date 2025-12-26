"""
Workflow Architect Service - The Constructor
Handles creation, updating, and reading workflow structures with Smart Upsert.
"""
import json
from typing import List, Dict, Any, Optional, Union

from app.core.client import get_client, safe_tool
from app.core.config import settings
from app.core.logging import architect_logger as logger


def _parse_json_safe(data: Union[str, List, Dict], field_name: str) -> Union[List, Dict]:
    """
    Smart parser: accepts both JSON strings and native Python objects.
    Provides detailed error messages on parse failure.
    """
    if isinstance(data, (list, dict)):
        return data
    
    try:
        return json.loads(data)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in '{field_name}': {e.msg} at line {e.lineno}, column {e.colno}. "
            f"Character position: {e.pos}. Content preview: '{data[max(0, e.pos-20):e.pos+20]}...'"
        )


async def _find_workflow_by_name(name: str) -> Optional[str]:
    """
    Search for a workflow by name and return its ID if found.
    Used for Smart Upsert logic.
    """
    client = get_client()
    data = await client.get("/workflows")
    workflows = data.get("data", [])
    
    for wf in workflows:
        if wf.get("name", "").lower() == name.lower():
            logger.info(f"Found existing workflow '{name}' with ID: {wf['id']}")
            return wf["id"]
    
    return None


@safe_tool
async def read_workflow_structure(workflow_id: str) -> str:
    """
    Get the full JSON structure (nodes & connections) of a workflow.
    Vital for reverse-engineering or analyzing existing bots.
    
    Args:
        workflow_id: The ID of the workflow to read.
    
    Returns:
        JSON string with the complete workflow specification.
    """
    logger.info(f"Reading workflow structure: {workflow_id}")
    client = get_client()
    data = await client.get(f"/workflows/{workflow_id}")
    return json.dumps(data, indent=2)


@safe_tool
async def deploy_workflow(
    name: str,
    nodes: Union[str, List[Dict[str, Any]]],
    connections: Union[str, Dict[str, Any]],
    activate: bool = False
) -> str:
    """
    Smart Upsert: Create or Update a workflow.
    - If a workflow with the same name exists, UPDATE it.
    - If not, CREATE a new one.
    
    Args:
        name: Name of the workflow.
        nodes: List of node definitions (can be JSON string or list).
        connections: Connection mapping between nodes (can be JSON string or dict).
        activate: Whether to activate the workflow after deployment.
    
    Returns:
        JSON string with deployment result including browser URL.
    """
    # Smart parsing with detailed error messages
    parsed_nodes = _parse_json_safe(nodes, "nodes")
    parsed_connections = _parse_json_safe(connections, "connections")
    
    # Validation
    if not parsed_nodes or not isinstance(parsed_nodes, list):
        raise ValueError("Nodes must be a non-empty list of node definitions.")
    
    logger.info(f"Deploying workflow: '{name}' with {len(parsed_nodes)} nodes")
    
    # Smart Upsert: Check if workflow exists
    existing_id = await _find_workflow_by_name(name)
    
    payload = {
        "name": name,
        "nodes": parsed_nodes,
        "connections": parsed_connections,
        "settings": {
            "saveManualExecutions": True,
            "saveExecutionProgress": True
        }
    }
    
    client = get_client()
    
    if existing_id:
        # UPDATE existing workflow
        logger.info(f"Updating existing workflow {existing_id}")
        data = await client.put(f"/workflows/{existing_id}", json_data=payload)
        action = "updated"
        workflow_id = existing_id
    else:
        # CREATE new workflow
        logger.info("Creating new workflow")
        data = await client.post("/workflows", json_data=payload)
        action = "created"
        workflow_id = data["id"]
    
    # Activate if requested
    if activate:
        logger.info(f"Activating workflow {workflow_id}")
        await client.post(f"/workflows/{workflow_id}/activate")
    
    # Build browser URL
    editor_url = f"{settings.n8n_editor_url}/workflow/{workflow_id}"
    
    result = {
        "status": "success",
        "action": action,
        "id": workflow_id,
        "name": data.get("name", name),
        "active": activate,
        "editor_url": editor_url,
        "node_count": len(parsed_nodes)
    }
    
    logger.info(f"Workflow {action}: {workflow_id} → {editor_url}")
    return json.dumps(result, indent=2)


@safe_tool
async def clone_workflow(source_id: str, new_name: str, activate: bool = False) -> str:
    """
    Clone an existing workflow with a new name.
    
    Args:
        source_id: ID of the workflow to clone.
        new_name: Name for the cloned workflow.
        activate: Whether to activate the cloned workflow.
    
    Returns:
        JSON string with the new workflow details.
    """
    logger.info(f"Cloning workflow {source_id} as '{new_name}'")
    
    # Read source workflow
    client = get_client()
    source = await client.get(f"/workflows/{source_id}")
    
    # Deploy as new workflow
    return await deploy_workflow(
        name=new_name,
        nodes=source.get("nodes", []),
        connections=source.get("connections", {}),
        activate=activate
    )
