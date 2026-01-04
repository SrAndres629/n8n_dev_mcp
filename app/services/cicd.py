"""
CI/CD & Version Control Service - Workflow Lifecycle Management
Enables Git synchronization, testing, and version control for n8n workflows.
"""
import json
import os
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional, Union, List

from app.core.client import get_client, safe_tool
from app.core.config import settings
from app.core.logging import gateway_logger as logger


def _get_backup_dir() -> str:
    """Get or create the workflow backup directory."""
    backup_dir = os.path.join(settings.n8n_data_dir, "workflow_backups")
    os.makedirs(backup_dir, exist_ok=True)
    return backup_dir


def _get_git_repo_dir() -> str:
    """Get or create the git repository directory for workflows."""
    git_dir = os.path.join(settings.n8n_data_dir, "workflow_repo")
    os.makedirs(git_dir, exist_ok=True)
    return git_dir


def _run_git_command(cmd: List[str], cwd: str) -> tuple:
    """Run a git command and return (success, output)."""
    try:
        result = subprocess.run(
            ["git"] + cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            shell=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout or result.stderr
    except Exception as e:
        return False, str(e)


@safe_tool
async def create_workflow_snapshot(
    workflow_id: str,
    description: Optional[str] = None
) -> str:
    """
    Create a versioned backup/snapshot of a workflow.
    Saves the complete workflow JSON to local storage.
    
    Args:
        workflow_id: ID of the workflow to snapshot.
        description: Optional description for this snapshot.
    
    Returns:
        JSON string with snapshot details.
    """
    logger.info(f"Creating snapshot for workflow: {workflow_id}")
    
    client = get_client()
    
    try:
        # Get workflow data
        workflow = await client.get(f"/workflows/{workflow_id}")
        workflow_name = workflow.get("name", "unknown")
        
        # Create snapshot file
        backup_dir = _get_backup_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() else "_" for c in workflow_name)
        filename = f"{safe_name}_{workflow_id}_{timestamp}.json"
        filepath = os.path.join(backup_dir, filename)
        
        # Add metadata
        snapshot_data = {
            "snapshot_metadata": {
                "created_at": datetime.now().isoformat(),
                "description": description or "Manual snapshot",
                "workflow_id": workflow_id,
                "workflow_name": workflow_name
            },
            "workflow": workflow
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot_data, f, indent=2)
        
        logger.info(f"Snapshot created: {filename}")
        
        return json.dumps({
            "status": "success",
            "action": "snapshot_created",
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "snapshot_file": filename,
            "snapshot_path": filepath,
            "created_at": timestamp
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error creating snapshot: {e}")
        return json.dumps({
            "status": "error",
            "workflow_id": workflow_id,
            "error": str(e)
        }, indent=2)


@safe_tool
async def list_workflow_snapshots(workflow_id: Optional[str] = None) -> str:
    """
    List all workflow snapshots, optionally filtered by workflow ID.
    
    Args:
        workflow_id: Optional workflow ID to filter snapshots.
    
    Returns:
        JSON string with list of available snapshots.
    """
    logger.info(f"Listing workflow snapshots" + (f" for {workflow_id}" if workflow_id else ""))
    
    backup_dir = _get_backup_dir()
    
    try:
        snapshots = []
        for filename in os.listdir(backup_dir):
            if not filename.endswith(".json"):
                continue
            
            filepath = os.path.join(backup_dir, filename)
            
            # Filter by workflow_id if specified
            if workflow_id and workflow_id not in filename:
                continue
            
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                metadata = data.get("snapshot_metadata", {})
                snapshots.append({
                    "filename": filename,
                    "workflow_id": metadata.get("workflow_id"),
                    "workflow_name": metadata.get("workflow_name"),
                    "created_at": metadata.get("created_at"),
                    "description": metadata.get("description"),
                    "size_bytes": os.path.getsize(filepath)
                })
            except:
                # Skip invalid files
                pass
        
        # Sort by creation date
        snapshots.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return json.dumps({
            "status": "success",
            "count": len(snapshots),
            "backup_directory": backup_dir,
            "snapshots": snapshots
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error listing snapshots: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)


@safe_tool
async def restore_workflow_from_snapshot(
    snapshot_filename: str,
    new_name: Optional[str] = None
) -> str:
    """
    Restore a workflow from a snapshot file.
    
    Args:
        snapshot_filename: Name of the snapshot file to restore.
        new_name: Optional new name for the restored workflow.
    
    Returns:
        JSON string with restored workflow details.
    """
    logger.info(f"Restoring workflow from snapshot: {snapshot_filename}")
    
    backup_dir = _get_backup_dir()
    filepath = os.path.join(backup_dir, snapshot_filename)
    
    if not os.path.exists(filepath):
        return json.dumps({
            "status": "error",
            "error": f"Snapshot file not found: {snapshot_filename}"
        }, indent=2)
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            snapshot_data = json.load(f)
        
        workflow = snapshot_data.get("workflow", {})
        
        # Prepare workflow for deployment
        workflow_name = new_name or workflow.get("name", "Restored Workflow")
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        client = get_client()
        
        # Create as new workflow
        payload = {
            "name": workflow_name,
            "nodes": nodes,
            "connections": connections,
            "settings": workflow.get("settings", {})
        }
        
        result = await client.post("/workflows", json_data=payload)
        
        logger.info(f"Workflow restored: {result.get('id')}")
        
        return json.dumps({
            "status": "success",
            "action": "restored",
            "new_workflow_id": result.get("id"),
            "workflow_name": workflow_name,
            "restored_from": snapshot_filename,
            "node_count": len(nodes)
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error restoring snapshot: {e}")
        return json.dumps({
            "status": "error",
            "snapshot_file": snapshot_filename,
            "error": str(e)
        }, indent=2)


@safe_tool
async def sync_workflows_to_git(
    repo_path: Optional[str] = None,
    commit_message: Optional[str] = None
) -> str:
    """
    Export all workflows to a local Git repository.
    Creates a commit with all current workflow states.
    
    Args:
        repo_path: Optional path to git repository (defaults to n8n_data/workflow_repo).
        commit_message: Optional commit message.
    
    Returns:
        JSON string with sync results.
    """
    logger.info("Syncing workflows to Git repository")
    
    repo_dir = repo_path or _get_git_repo_dir()
    workflows_dir = os.path.join(repo_dir, "workflows")
    os.makedirs(workflows_dir, exist_ok=True)
    
    client = get_client()
    
    try:
        # Initialize git repo if needed
        git_init_path = os.path.join(repo_dir, ".git")
        if not os.path.exists(git_init_path):
            success, output = _run_git_command(["init"], repo_dir)
            if not success:
                return json.dumps({
                    "status": "error",
                    "error": f"Failed to initialize git repo: {output}"
                }, indent=2)
            logger.info("Initialized new git repository")
        
        # Get all workflows
        data = await client.get("/workflows")
        workflows = data.get("data", [])
        
        exported_files = []
        for wf in workflows:
            workflow_id = wf.get("id")
            workflow_name = wf.get("name", "unknown")
            
            # Get full workflow data
            full_wf = await client.get(f"/workflows/{workflow_id}")
            
            # Create safe filename
            safe_name = "".join(c if c.isalnum() else "_" for c in workflow_name)
            filename = f"{safe_name}_{workflow_id}.json"
            filepath = os.path.join(workflows_dir, filename)
            
            # Remove sensitive data before saving
            export_data = {
                "id": workflow_id,
                "name": workflow_name,
                "nodes": full_wf.get("nodes", []),
                "connections": full_wf.get("connections", {}),
                "settings": full_wf.get("settings", {}),
                "staticData": full_wf.get("staticData"),
                "active": full_wf.get("active"),
                "synced_at": datetime.now().isoformat()
            }
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2)
            
            exported_files.append(filename)
        
        # Git add and commit
        _run_git_command(["add", "."], repo_dir)
        
        msg = commit_message or f"Sync {len(workflows)} workflows - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        success, output = _run_git_command(["commit", "-m", msg], repo_dir)
        
        commit_status = "committed" if success else "no_changes"
        
        logger.info(f"Synced {len(exported_files)} workflows to git")
        
        return json.dumps({
            "status": "success",
            "action": "synced",
            "repository_path": repo_dir,
            "workflows_exported": len(exported_files),
            "files": exported_files,
            "git_status": commit_status,
            "commit_message": msg if success else "No changes to commit"
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error syncing to git: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)


@safe_tool
async def import_workflow_from_git(
    filename: str,
    repo_path: Optional[str] = None,
    activate: bool = False
) -> str:
    """
    Import a workflow from the Git repository.
    
    Args:
        filename: Name of the workflow file to import.
        repo_path: Optional path to git repository.
        activate: Whether to activate the workflow after import.
    
    Returns:
        JSON string with import results.
    """
    logger.info(f"Importing workflow from git: {filename}")
    
    repo_dir = repo_path or _get_git_repo_dir()
    workflows_dir = os.path.join(repo_dir, "workflows")
    filepath = os.path.join(workflows_dir, filename)
    
    if not os.path.exists(filepath):
        return json.dumps({
            "status": "error",
            "error": f"File not found: {filename}"
        }, indent=2)
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            workflow_data = json.load(f)
        
        client = get_client()
        
        payload = {
            "name": workflow_data.get("name"),
            "nodes": workflow_data.get("nodes", []),
            "connections": workflow_data.get("connections", {}),
            "settings": workflow_data.get("settings", {})
        }
        
        result = await client.post("/workflows", json_data=payload)
        new_id = result.get("id")
        
        if activate:
            await client.post(f"/workflows/{new_id}/activate")
        
        logger.info(f"Imported workflow: {new_id}")
        
        return json.dumps({
            "status": "success",
            "action": "imported",
            "workflow_id": new_id,
            "workflow_name": workflow_data.get("name"),
            "imported_from": filename,
            "activated": activate
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error importing from git: {e}")
        return json.dumps({
            "status": "error",
            "filename": filename,
            "error": str(e)
        }, indent=2)


@safe_tool
async def workflow_unit_test(
    workflow_id: str,
    test_payload: Union[str, Dict[str, Any]],
    expected_output: Optional[Union[str, Dict[str, Any]]] = None,
    timeout_seconds: int = 30
) -> str:
    """
    Send a test payload to a workflow and verify the output.
    
    Args:
        workflow_id: ID of the workflow to test.
        test_payload: Input data to send to the workflow.
        expected_output: Optional expected output to verify against.
        timeout_seconds: Maximum time to wait for execution.
    
    Returns:
        JSON string with test results.
    """
    logger.info(f"Running unit test for workflow: {workflow_id}")
    
    # Parse payloads
    if isinstance(test_payload, str):
        try:
            parsed_payload = json.loads(test_payload)
        except json.JSONDecodeError as e:
            return json.dumps({
                "status": "error",
                "error": f"Invalid test payload JSON: {e}"
            }, indent=2)
    else:
        parsed_payload = test_payload
    
    parsed_expected = None
    if expected_output:
        if isinstance(expected_output, str):
            try:
                parsed_expected = json.loads(expected_output)
            except:
                parsed_expected = expected_output
        else:
            parsed_expected = expected_output
    
    client = get_client()
    
    try:
        import time
        start_time = time.time()
        
        # Trigger the workflow
        result = await client.post(
            f"/workflows/{workflow_id}/run",
            json_data={"data": parsed_payload}
        )
        
        execution_id = result.get("id") or result.get("executionId")
        
        if not execution_id:
            return json.dumps({
                "status": "error",
                "error": "No execution ID returned"
            }, indent=2)
        
        # Poll for execution completion
        execution_result = None
        while time.time() - start_time < timeout_seconds:
            execution = await client.get(f"/executions/{execution_id}")
            status = execution.get("status")
            
            if status in ["success", "finished", "error"]:
                execution_result = execution
                break
            
            time.sleep(1)
        
        if not execution_result:
            return json.dumps({
                "status": "timeout",
                "execution_id": execution_id,
                "message": f"Execution did not complete within {timeout_seconds} seconds"
            }, indent=2)
        
        # Extract output
        run_data = execution_result.get("data", {}).get("resultData", {}).get("runData", {})
        output_data = None
        
        # Get output from last node
        for node_name, runs in run_data.items():
            if runs and len(runs) > 0:
                last_run = runs[-1]
                if last_run.get("data"):
                    output_data = last_run.get("data")
        
        execution_time = time.time() - start_time
        
        # Compare with expected if provided
        test_passed = None
        if parsed_expected is not None:
            # Simple comparison (can be enhanced for partial matching)
            test_passed = output_data == parsed_expected
        
        result = {
            "status": "success" if test_passed is not False else "failed",
            "execution_id": execution_id,
            "execution_status": execution_result.get("status"),
            "execution_time_seconds": round(execution_time, 2),
            "input": parsed_payload,
            "output": output_data
        }
        
        if parsed_expected is not None:
            result["expected_output"] = parsed_expected
            result["test_passed"] = test_passed
        
        return json.dumps(result, indent=2, default=str)
        
    except Exception as e:
        logger.error(f"Error running unit test: {e}")
        return json.dumps({
            "status": "error",
            "workflow_id": workflow_id,
            "error": str(e)
        }, indent=2)


@safe_tool
async def shadow_test_workflow(
    workflow_id: str,
    test_count: int = 5
) -> str:
    """
    Create a shadow copy of a workflow and run it with recent execution data.
    Tests changes without affecting production.
    
    Args:
        workflow_id: ID of the workflow to shadow test.
        test_count: Number of recent executions to replay.
    
    Returns:
        JSON string with shadow test results.
    """
    logger.info(f"Running shadow test for workflow: {workflow_id}")
    
    client = get_client()
    
    try:
        # Get original workflow
        original = await client.get(f"/workflows/{workflow_id}")
        original_name = original.get("name", "Unknown")
        
        # Create shadow copy
        shadow_name = f"[SHADOW] {original_name}"
        shadow_payload = {
            "name": shadow_name,
            "nodes": original.get("nodes", []),
            "connections": original.get("connections", {}),
            "settings": original.get("settings", {})
        }
        
        shadow_result = await client.post("/workflows", json_data=shadow_payload)
        shadow_id = shadow_result.get("id")
        
        # Get recent executions from original
        executions_data = await client.get(
            f"/executions",
            params={"workflowId": workflow_id, "limit": test_count, "status": "success"}
        )
        executions = executions_data.get("data", [])
        
        test_results = []
        for exec_data in executions:
            exec_id = exec_data.get("id")
            
            # Get execution details
            execution = await client.get(f"/executions/{exec_id}")
            
            # Extract trigger data
            run_data = execution.get("data", {}).get("resultData", {}).get("runData", {})
            trigger_data = {}
            for node_name, runs in run_data.items():
                if runs and len(runs) > 0:
                    trigger_data = runs[0].get("data", {})
                    break
            
            # Run on shadow workflow
            try:
                shadow_exec = await client.post(
                    f"/workflows/{shadow_id}/run",
                    json_data={"data": trigger_data}
                )
                test_results.append({
                    "original_execution": exec_id,
                    "shadow_execution": shadow_exec.get("id"),
                    "status": "triggered"
                })
            except Exception as e:
                test_results.append({
                    "original_execution": exec_id,
                    "error": str(e)
                })
        
        logger.info(f"Shadow test complete: {len(test_results)} executions replayed")
        
        return json.dumps({
            "status": "success",
            "original_workflow_id": workflow_id,
            "original_workflow_name": original_name,
            "shadow_workflow_id": shadow_id,
            "shadow_workflow_name": shadow_name,
            "tests_run": len(test_results),
            "results": test_results,
            "note": "Remember to delete the shadow workflow after testing"
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error in shadow test: {e}")
        return json.dumps({
            "status": "error",
            "workflow_id": workflow_id,
            "error": str(e)
        }, indent=2)


@safe_tool
async def compare_workflow_versions(
    workflow_id: str,
    snapshot_filename: str
) -> str:
    """
    Compare current workflow state with a snapshot version.
    
    Args:
        workflow_id: ID of the current workflow.
        snapshot_filename: Name of the snapshot to compare against.
    
    Returns:
        JSON string with comparison results (diff).
    """
    logger.info(f"Comparing workflow {workflow_id} with snapshot {snapshot_filename}")
    
    backup_dir = _get_backup_dir()
    filepath = os.path.join(backup_dir, snapshot_filename)
    
    if not os.path.exists(filepath):
        return json.dumps({
            "status": "error",
            "error": f"Snapshot not found: {snapshot_filename}"
        }, indent=2)
    
    client = get_client()
    
    try:
        # Get current workflow
        current = await client.get(f"/workflows/{workflow_id}")
        
        # Load snapshot
        with open(filepath, "r", encoding="utf-8") as f:
            snapshot_data = json.load(f)
        
        snapshot_workflow = snapshot_data.get("workflow", {})
        
        # Compare nodes
        current_nodes = {n.get("name"): n for n in current.get("nodes", [])}
        snapshot_nodes = {n.get("name"): n for n in snapshot_workflow.get("nodes", [])}
        
        added_nodes = [n for n in current_nodes if n not in snapshot_nodes]
        removed_nodes = [n for n in snapshot_nodes if n not in current_nodes]
        
        modified_nodes = []
        for name in current_nodes:
            if name in snapshot_nodes:
                if current_nodes[name] != snapshot_nodes[name]:
                    modified_nodes.append(name)
        
        # Compare connections
        current_conn = json.dumps(current.get("connections", {}), sort_keys=True)
        snapshot_conn = json.dumps(snapshot_workflow.get("connections", {}), sort_keys=True)
        connections_changed = current_conn != snapshot_conn
        
        return json.dumps({
            "status": "success",
            "workflow_id": workflow_id,
            "snapshot_file": snapshot_filename,
            "changes_detected": bool(added_nodes or removed_nodes or modified_nodes or connections_changed),
            "diff": {
                "nodes_added": added_nodes,
                "nodes_removed": removed_nodes,
                "nodes_modified": modified_nodes,
                "connections_changed": connections_changed
            },
            "current_node_count": len(current_nodes),
            "snapshot_node_count": len(snapshot_nodes)
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error comparing versions: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)
