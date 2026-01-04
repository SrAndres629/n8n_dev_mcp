"""
Live State Surgery Service - Real-Time Workflow Intervention
Enables injection of data into running workflows and re-execution of failed nodes.
"""
import json
from typing import Dict, Any, Optional, Union, List

from app.core.client import get_client, safe_tool
from app.core.logging import gateway_logger as logger


@safe_tool
async def get_waiting_executions(workflow_id: Optional[str] = None) -> str:
    """
    Get executions that are in 'waiting' status (paused, awaiting input).
    
    Args:
        workflow_id: Optional workflow ID to filter by.
    
    Returns:
        JSON string with list of waiting executions.
    """
    logger.info(f"Fetching waiting executions" + (f" for workflow {workflow_id}" if workflow_id else ""))
    
    client = get_client()
    params = {"status": "waiting"}
    if workflow_id:
        params["workflowId"] = workflow_id
    
    try:
        data = await client.get("/executions", params=params)
        executions = data.get("data", [])
        
        result = []
        for exec_data in executions:
            result.append({
                "id": exec_data.get("id"),
                "workflow_id": exec_data.get("workflowId"),
                "workflow_name": exec_data.get("workflowData", {}).get("name"),
                "status": exec_data.get("status"),
                "started_at": exec_data.get("startedAt"),
                "waiting_since": exec_data.get("stoppedAt"),
                "mode": exec_data.get("mode")
            })
        
        return json.dumps({
            "status": "success",
            "count": len(result),
            "executions": result
        }, indent=2)
    except Exception as e:
        logger.error(f"Error fetching waiting executions: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)


@safe_tool
async def trigger_workflow_now(
    workflow_id: str,
    payload: Optional[Union[str, Dict[str, Any]]] = None
) -> str:
    """
    Manually trigger a workflow with an optional custom payload.
    Works for both webhook-triggered and manual trigger workflows.
    
    Args:
        workflow_id: ID of the workflow to trigger.
        payload: Optional JSON payload to send (can be string or dict).
    
    Returns:
        JSON string with execution details.
    """
    logger.info(f"Manually triggering workflow: {workflow_id}")
    
    # Parse payload if string
    if isinstance(payload, str):
        try:
            parsed_payload = json.loads(payload)
        except json.JSONDecodeError as e:
            return json.dumps({
                "status": "error",
                "error": f"Invalid JSON in payload: {e}"
            }, indent=2)
    else:
        parsed_payload = payload or {}
    
    client = get_client()
    
    try:
        # First, get workflow details to check trigger type
        workflow = await client.get(f"/workflows/{workflow_id}")
        workflow_name = workflow.get("name", "Unknown")
        
        # Try to execute via the executions endpoint (manual trigger)
        # This triggers the workflow as if pressing "Execute" in the UI
        data = await client.post(
            f"/workflows/{workflow_id}/run",
            json_data={"data": parsed_payload}
        )
        
        logger.info(f"Successfully triggered workflow: {workflow_name}")
        
        return json.dumps({
            "status": "success",
            "action": "triggered",
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "execution_id": data.get("id") or data.get("executionId"),
            "payload_sent": parsed_payload
        }, indent=2)
        
    except Exception as e:
        error_msg = str(e)
        
        # If /run doesn't work, try webhook approach
        if "webhook" in workflow_name.lower() or "404" in error_msg:
            # Try to find webhook path
            try:
                nodes = workflow.get("nodes", [])
                webhook_nodes = [n for n in nodes if "webhook" in n.get("type", "").lower()]
                
                if webhook_nodes:
                    webhook_path = webhook_nodes[0].get("parameters", {}).get("path")
                    return json.dumps({
                        "status": "info",
                        "message": "This workflow uses a webhook trigger",
                        "webhook_path": webhook_path,
                        "suggestion": f"Hit the webhook URL directly with your payload"
                    }, indent=2)
            except:
                pass
        
        logger.error(f"Error triggering workflow: {e}")
        return json.dumps({
            "status": "error",
            "workflow_id": workflow_id,
            "error": error_msg
        }, indent=2)


@safe_tool
async def inject_execution_data(
    execution_id: str,
    node_name: str,
    data: Union[str, Dict[str, Any]]
) -> str:
    """
    Inject data into a waiting/paused execution at a specific node.
    Useful for workflows that are waiting for external input.
    
    Args:
        execution_id: ID of the waiting execution.
        node_name: Name of the node to inject data into.
        data: JSON data to inject (string or dict).
    
    Returns:
        JSON string with operation result.
    """
    logger.info(f"Injecting data into execution {execution_id} at node '{node_name}'")
    
    # Parse data if string
    if isinstance(data, str):
        try:
            parsed_data = json.loads(data)
        except json.JSONDecodeError as e:
            return json.dumps({
                "status": "error",
                "error": f"Invalid JSON data: {e}"
            }, indent=2)
    else:
        parsed_data = data
    
    client = get_client()
    
    try:
        # Get current execution state
        execution = await client.get(f"/executions/{execution_id}")
        
        if execution.get("status") not in ["waiting", "running"]:
            return json.dumps({
                "status": "error",
                "error": f"Execution is not in waiting state. Current status: {execution.get('status')}"
            }, indent=2)
        
        # Send data to the execution
        result = await client.post(
            f"/executions/{execution_id}/data",
            json_data={
                "nodeName": node_name,
                "data": parsed_data
            }
        )
        
        logger.info(f"Successfully injected data into execution {execution_id}")
        
        return json.dumps({
            "status": "success",
            "action": "data_injected",
            "execution_id": execution_id,
            "node_name": node_name,
            "data_injected": parsed_data
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error injecting data: {e}")
        return json.dumps({
            "status": "error",
            "execution_id": execution_id,
            "error": str(e)
        }, indent=2)


@safe_tool
async def rerun_node_with_patch(
    execution_id: str,
    node_name: str,
    patched_input: Union[str, Dict[str, Any]]
) -> str:
    """
    Re-execute a failed node with corrected input data.
    Creates a new execution starting from the specified node with patched data.
    
    Args:
        execution_id: ID of the failed execution to analyze.
        node_name: Name of the node that failed.
        patched_input: Corrected input data for the node (JSON string or dict).
    
    Returns:
        JSON string with new execution details.
    """
    logger.info(f"Re-running node '{node_name}' from execution {execution_id} with patched input")
    
    # Parse patched input
    if isinstance(patched_input, str):
        try:
            parsed_input = json.loads(patched_input)
        except json.JSONDecodeError as e:
            return json.dumps({
                "status": "error",
                "error": f"Invalid JSON in patched_input: {e}"
            }, indent=2)
    else:
        parsed_input = patched_input
    
    client = get_client()
    
    try:
        # Get the original execution
        execution = await client.get(f"/executions/{execution_id}")
        
        workflow_id = execution.get("workflowId")
        workflow_data = execution.get("workflowData", {})
        run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
        
        # Find the node and its position in the workflow
        nodes = workflow_data.get("nodes", [])
        target_node = None
        for node in nodes:
            if node.get("name") == node_name:
                target_node = node
                break
        
        if not target_node:
            return json.dumps({
                "status": "error",
                "error": f"Node '{node_name}' not found in workflow"
            }, indent=2)
        
        # Create a modified workflow execution
        # We'll re-trigger the workflow with the patched data as initial input
        
        result = await client.post(
            f"/workflows/{workflow_id}/run",
            json_data={
                "startNodes": [node_name],
                "data": parsed_input
            }
        )
        
        logger.info(f"Successfully created new execution with patched input")
        
        return json.dumps({
            "status": "success",
            "action": "rerun_with_patch",
            "original_execution_id": execution_id,
            "new_execution_id": result.get("id") or result.get("executionId"),
            "workflow_id": workflow_id,
            "node_name": node_name,
            "patched_input": parsed_input
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error re-running node: {e}")
        return json.dumps({
            "status": "error",
            "execution_id": execution_id,
            "error": str(e)
        }, indent=2)


@safe_tool
async def get_execution_data(execution_id: str) -> str:
    """
    Get complete execution data including input/output for all nodes.
    Useful for understanding what data flowed through each node.
    
    Args:
        execution_id: ID of the execution to analyze.
    
    Returns:
        JSON string with detailed execution data.
    """
    logger.info(f"Fetching execution data for: {execution_id}")
    
    client = get_client()
    
    try:
        execution = await client.get(f"/executions/{execution_id}")
        
        # Extract useful info
        run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
        
        node_results = {}
        for node_name, node_runs in run_data.items():
            if node_runs and len(node_runs) > 0:
                last_run = node_runs[-1]
                node_results[node_name] = {
                    "status": "success" if not last_run.get("error") else "error",
                    "started_at": last_run.get("startTime"),
                    "finished_at": last_run.get("executionTime"),
                    "input_data": last_run.get("inputData"),
                    "output_data": last_run.get("data"),
                    "error": last_run.get("error")
                }
        
        return json.dumps({
            "status": "success",
            "execution_id": execution_id,
            "workflow_id": execution.get("workflowId"),
            "workflow_name": execution.get("workflowData", {}).get("name"),
            "execution_status": execution.get("status"),
            "started_at": execution.get("startedAt"),
            "finished_at": execution.get("stoppedAt"),
            "mode": execution.get("mode"),
            "node_results": node_results
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error fetching execution data: {e}")
        return json.dumps({
            "status": "error",
            "execution_id": execution_id,
            "error": str(e)
        }, indent=2)


@safe_tool
async def retry_failed_execution(execution_id: str) -> str:
    """
    Retry a failed execution from the beginning.
    
    Args:
        execution_id: ID of the failed execution to retry.
    
    Returns:
        JSON string with new execution details.
    """
    logger.info(f"Retrying failed execution: {execution_id}")
    
    client = get_client()
    
    try:
        # Get original execution
        execution = await client.get(f"/executions/{execution_id}")
        
        if execution.get("status") != "error":
            return json.dumps({
                "status": "warning",
                "message": f"Execution status is '{execution.get('status')}', not 'error'. Proceeding anyway."
            }, indent=2)
        
        workflow_id = execution.get("workflowId")
        
        # Get the original trigger data if available
        run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
        original_data = {}
        
        # Try to find trigger node data
        for node_name, node_runs in run_data.items():
            if "trigger" in node_name.lower() or "webhook" in node_name.lower():
                if node_runs and len(node_runs) > 0:
                    original_data = node_runs[0].get("data", {})
                    break
        
        # Trigger new execution
        result = await client.post(
            f"/workflows/{workflow_id}/run",
            json_data={"data": original_data}
        )
        
        logger.info(f"Successfully retried execution, new ID: {result.get('id')}")
        
        return json.dumps({
            "status": "success",
            "action": "retried",
            "original_execution_id": execution_id,
            "new_execution_id": result.get("id") or result.get("executionId"),
            "workflow_id": workflow_id
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error retrying execution: {e}")
        return json.dumps({
            "status": "error",
            "execution_id": execution_id,
            "error": str(e)
        }, indent=2)
