"""
Workflow Debugger Service - The Doctor
Handles execution analysis and deep error diagnosis for auto-healing.
"""
import json
from typing import Optional, List, Dict, Any

from app.core.client import get_client, safe_tool
from app.core.logging import debugger_logger as logger


def _extract_error_details(execution_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep dive into execution data to extract precise error information.
    Navigates through resultData.runData to find the failing node.
    """
    error_info = {
        "failed_node": "Unknown",
        "node_type": "Unknown",
        "error_type": "Unknown",
        "error_message": "No error details available",
        "stack_trace": None,
        "input_data": None
    }
    
    if "data" not in execution_data:
        return error_info
    
    result_data = execution_data["data"].get("resultData", {})
    
    # Primary error location (top-level error object)
    if "error" in result_data:
        top_error = result_data["error"]
        error_info["failed_node"] = top_error.get("node", {}).get("name", "Unknown Node")
        error_info["node_type"] = top_error.get("node", {}).get("type", "Unknown")
        error_info["error_message"] = top_error.get("message", "No message")
        error_info["stack_trace"] = top_error.get("stack")
        
        # Try to get error type from description
        if "description" in top_error:
            error_info["error_type"] = top_error["description"]
    
    # Deep dive into runData for more details
    run_data = result_data.get("runData", {})
    
    for node_name, node_runs in run_data.items():
        for run_index, run in enumerate(node_runs):
            if "error" in run:
                node_error = run["error"]
                
                # This is the failing node
                error_info["failed_node"] = node_name
                
                if isinstance(node_error, dict):
                    error_info["error_message"] = node_error.get("message", str(node_error))
                    error_info["error_type"] = node_error.get("name", "Error")
                    error_info["stack_trace"] = node_error.get("stack")
                else:
                    error_info["error_message"] = str(node_error)
                
                # Extract input data that caused the failure
                if "inputData" in run:
                    error_info["input_data"] = run["inputData"]
                elif "source" in run:
                    error_info["input_data"] = run["source"]
                
                # Found the error, no need to continue
                break
    
    return error_info


@safe_tool
async def diagnose_execution(execution_id: str) -> str:
    """
    Deep dive diagnosis of a specific execution.
    Navigates the execution JSON to find exactly what failed and why.
    
    Args:
        execution_id: The ID of the execution to analyze.
    
    Returns:
        JSON string with detailed diagnosis including:
        - Failed node name and type
        - Error type and message
        - Input data that caused the failure
        - Stack trace (if available)
    """
    logger.info(f"Diagnosing execution: {execution_id}")
    
    client = get_client()
    execution = await client.get(f"/executions/{execution_id}", params={"includeData": "true"})
    
    # Extract workflow info
    workflow_info = {
        "workflow_id": execution.get("workflowId"),
        "workflow_name": execution.get("workflowData", {}).get("name", "Unknown"),
        "started_at": execution.get("startedAt"),
        "finished_at": execution.get("stoppedAt"),
        "status": execution.get("status"),
        "mode": execution.get("mode")
    }
    
    # Deep dive for error details
    error_details = _extract_error_details(execution)
    
    diagnosis = {
        "execution_id": execution_id,
        "workflow": workflow_info,
        "diagnosis": error_details,
        "recommendation": _generate_recommendation(error_details)
    }
    
    logger.info(f"Diagnosis complete: Node '{error_details['failed_node']}' failed with: {error_details['error_message'][:100]}")
    
    return json.dumps(diagnosis, indent=2)


def _generate_recommendation(error_info: Dict[str, Any]) -> str:
    """
    Generate an AI-friendly recommendation based on the error type.
    """
    message = error_info.get("error_message", "").lower()
    node = error_info.get("failed_node", "")
    
    if "404" in message or "not found" in message:
        return f"The endpoint or resource in node '{node}' returned 404. Check the URL path or resource ID."
    
    if "401" in message or "unauthorized" in message:
        return f"Authentication failed in node '{node}'. Verify API credentials or tokens."
    
    if "timeout" in message:
        return f"Node '{node}' timed out. Consider increasing timeout or checking endpoint availability."
    
    if "json" in message or "parse" in message:
        return f"Node '{node}' received invalid JSON. Check the data format from the previous node."
    
    if "undefined" in message or "property" in message:
        return f"Node '{node}' tried to access a missing property. Check input data structure."
    
    return f"Review the error in node '{node}' and verify its configuration and input data."


@safe_tool
async def analyze_execution_failures(
    workflow_id: Optional[str] = None,
    limit: int = 5
) -> str:
    """
    Analyze multiple failed executions to find patterns.
    
    Args:
        workflow_id: Optional workflow ID to filter by.
        limit: Maximum number of failed executions to analyze.
    
    Returns:
        JSON string with analysis of all failed executions.
    """
    logger.info(f"Analyzing up to {limit} failed executions" + (f" for workflow {workflow_id}" if workflow_id else ""))
    
    params = {
        "includeData": "true",
        "status": "error",
        "limit": limit
    }
    if workflow_id:
        params["workflowId"] = workflow_id
    
    client = get_client()
    data = await client.get("/executions", params=params)
    executions = data.get("data", [])
    
    analyses = []
    for exc in executions:
        error_details = _extract_error_details(exc)
        
        analyses.append({
            "execution_id": exc["id"],
            "workflow_id": exc.get("workflowId"),
            "workflow_name": exc.get("workflowData", {}).get("name"),
            "started_at": exc.get("startedAt"),
            "failed_node": error_details["failed_node"],
            "error_type": error_details["error_type"],
            "error_message": error_details["error_message"],
            "recommendation": _generate_recommendation(error_details)
        })
    
    logger.info(f"Analyzed {len(analyses)} failed executions")
    return json.dumps(analyses, indent=2)


@safe_tool
async def get_execution_history(
    workflow_id: Optional[str] = None,
    limit: int = 10,
    status: Optional[str] = None
) -> str:
    """
    Get execution history for workflows.
    
    Args:
        workflow_id: Optional workflow ID to filter by.
        limit: Maximum number of executions to return.
        status: Optional status filter ('success', 'error', 'waiting').
    
    Returns:
        JSON string with execution summaries.
    """
    params = {"limit": limit}
    if workflow_id:
        params["workflowId"] = workflow_id
    if status:
        params["status"] = status
    
    client = get_client()
    data = await client.get("/executions", params=params)
    executions = data.get("data", [])
    
    summaries = []
    for exc in executions:
        summaries.append({
            "id": exc["id"],
            "workflow_id": exc.get("workflowId"),
            "workflow_name": exc.get("workflowData", {}).get("name"),
            "status": exc.get("status"),
            "started_at": exc.get("startedAt"),
            "finished_at": exc.get("stoppedAt"),
            "mode": exc.get("mode")
        })
    
    return json.dumps(summaries, indent=2)
