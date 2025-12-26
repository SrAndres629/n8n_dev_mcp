"""
Workflow Manager Service
Handles listing, activation, and deletion of workflows.
"""
import json
from typing import List, Optional

from app.core.client import get_client, safe_tool
from app.core.logging import manager_logger as logger


@safe_tool
async def list_all_workflows(tags: Optional[List[str]] = None) -> str:
    """
    List all workflows, optionally filtering by tags.
    
    Args:
        tags: Optional list of tag names to filter by.
    
    Returns:
        JSON string with workflow summaries (ID, Name, Active, Tags).
    """
    logger.info("Listing all workflows" + (f" with tags: {tags}" if tags else ""))
    
    client = get_client()
    data = await client.get("/workflows")
    workflows = data.get("data", [])
    
    result = []
    for wf in workflows:
        wf_tags = [tag.get("name") for tag in wf.get("tags", [])]
        
        # Apply tag filter if specified
        if tags:
            if not any(tag in wf_tags for tag in tags):
                continue
        
        result.append({
            "id": wf["id"],
            "name": wf["name"],
            "active": wf["active"],
            "tags": wf_tags,
            "created_at": wf.get("createdAt"),
            "updated_at": wf.get("updatedAt")
        })
    
    logger.info(f"Found {len(result)} workflows")
    return json.dumps(result, indent=2)


@safe_tool
async def toggle_workflow_state(workflow_id: str, active: bool) -> str:
    """
    Activate or deactivate a workflow.
    
    Args:
        workflow_id: The ID of the workflow to toggle.
        active: True to activate, False to deactivate.
    
    Returns:
        JSON string with operation result.
    """
    action = "activate" if active else "deactivate"
    logger.info(f"Attempting to {action} workflow: {workflow_id}")
    
    client = get_client()
    endpoint = f"/workflows/{workflow_id}/{action}"
    await client.post(endpoint)
    
    logger.info(f"Successfully {action}d workflow: {workflow_id}")
    
    return json.dumps({
        "status": "success",
        "workflow_id": workflow_id,
        "action": action,
        "is_active": active
    }, indent=2)


@safe_tool
async def delete_workflow(workflow_id: str) -> str:
    """
    Permanently delete a workflow.
    
    Args:
        workflow_id: The ID of the workflow to delete.
    
    Returns:
        JSON string with operation result.
    """
    logger.info(f"Deleting workflow: {workflow_id}")
    
    client = get_client()
    await client.delete(f"/workflows/{workflow_id}")
    
    logger.info(f"Successfully deleted workflow: {workflow_id}")
    
    return json.dumps({
        "status": "success",
        "workflow_id": workflow_id,
        "message": f"Workflow {workflow_id} deleted successfully."
    }, indent=2)


@safe_tool
async def get_workflow_tags() -> str:
    """
    Get all available workflow tags.
    
    Returns:
        JSON string with list of tags.
    """
    logger.info("Fetching workflow tags")
    
    client = get_client()
    
    try:
        # Try to get tags directly (n8n 1.0+)
        data = await client.get("/tags")
        tags = data.get("data", [])
    except Exception:
        # Fallback: extract tags from workflows
        logger.info("Tags endpoint not available, extracting from workflows")
        data = await client.get("/workflows")
        workflows = data.get("data", [])
        
        tag_set = set()
        for wf in workflows:
            for tag in wf.get("tags", []):
                tag_set.add(tag.get("name"))
        
        tags = [{"name": t} for t in sorted(tag_set)]
    
    return json.dumps({
        "status": "success",
        "tags": tags
    }, indent=2)
