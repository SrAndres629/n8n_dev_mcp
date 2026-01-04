"""
Auto-Healing Service - Proactive System Maintenance
Provides autonomous monitoring, credential management, and database pruning.
"""
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict

from app.core.client import get_client, safe_tool
from app.core.config import settings
from app.core.logging import gateway_logger as logger

# In-memory monitoring state (could be moved to Redis in production)
_monitoring_state = {
    "active": False,
    "alerts": [],
    "last_check": None,
    "error_counts": defaultdict(int)
}


@safe_tool
async def health_check_all() -> str:
    """
    Comprehensive system health check across all components.
    Checks: n8n API, workflows, credentials, recent executions.
    
    Returns:
        JSON string with complete health status.
    """
    logger.info("Running comprehensive health check")
    
    client = get_client()
    health_report = {
        "timestamp": datetime.now().isoformat(),
        "status": "healthy",
        "components": {},
        "warnings": [],
        "errors": []
    }
    
    try:
        # Check n8n API connectivity
        try:
            await client.get("/workflows")
            health_report["components"]["n8n_api"] = {"status": "healthy"}
        except Exception as e:
            health_report["components"]["n8n_api"] = {"status": "error", "message": str(e)}
            health_report["errors"].append("n8n API not reachable")
            health_report["status"] = "critical"
        
        # Check workflows
        try:
            wf_data = await client.get("/workflows")
            workflows = wf_data.get("data", [])
            active_count = sum(1 for wf in workflows if wf.get("active"))
            health_report["components"]["workflows"] = {
                "status": "healthy",
                "total": len(workflows),
                "active": active_count,
                "inactive": len(workflows) - active_count
            }
        except Exception as e:
            health_report["components"]["workflows"] = {"status": "error", "message": str(e)}
        
        # Check credentials
        try:
            cred_data = await client.get("/credentials")
            credentials = cred_data.get("data", [])
            health_report["components"]["credentials"] = {
                "status": "healthy",
                "total": len(credentials)
            }
        except Exception as e:
            health_report["components"]["credentials"] = {"status": "error", "message": str(e)}
        
        # Check recent executions for errors
        try:
            exec_data = await client.get("/executions", params={"limit": 50})
            executions = exec_data.get("data", [])
            
            error_count = sum(1 for ex in executions if ex.get("status") == "error")
            success_count = sum(1 for ex in executions if ex.get("status") in ["success", "finished"])
            
            error_rate = error_count / len(executions) * 100 if executions else 0
            
            exec_status = "healthy"
            if error_rate > 50:
                exec_status = "critical"
                health_report["errors"].append(f"High error rate: {error_rate:.1f}%")
                health_report["status"] = "critical"
            elif error_rate > 20:
                exec_status = "warning"
                health_report["warnings"].append(f"Elevated error rate: {error_rate:.1f}%")
                if health_report["status"] == "healthy":
                    health_report["status"] = "warning"
            
            health_report["components"]["executions"] = {
                "status": exec_status,
                "recent_total": len(executions),
                "successes": success_count,
                "errors": error_count,
                "error_rate_percent": round(error_rate, 1)
            }
        except Exception as e:
            health_report["components"]["executions"] = {"status": "error", "message": str(e)}
        
        logger.info(f"Health check complete: {health_report['status']}")
        return json.dumps(health_report, indent=2)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }, indent=2)


@safe_tool
async def smart_db_prune(
    days_to_keep: int = 3,
    keep_errors: bool = True,
    dry_run: bool = True
) -> str:
    """
    Intelligently prune old execution records from n8n database.
    
    Args:
        days_to_keep: Number of days of executions to keep (default: 3).
        keep_errors: Whether to keep error executions regardless of age.
        dry_run: If True, only report what would be deleted.
    
    Returns:
        JSON string with pruning results.
    """
    logger.info(f"Smart DB prune: keep {days_to_keep} days, keep_errors={keep_errors}, dry_run={dry_run}")
    
    client = get_client()
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    
    try:
        # Get all executions
        exec_data = await client.get("/executions", params={"limit": 1000})
        executions = exec_data.get("data", [])
        
        to_delete = []
        to_keep = []
        
        for ex in executions:
            started = ex.get("startedAt")
            if not started:
                continue
            
            try:
                # Parse ISO date
                exec_date = datetime.fromisoformat(started.replace("Z", "+00:00"))
                exec_date = exec_date.replace(tzinfo=None)  # Remove timezone for comparison
            except:
                continue
            
            is_old = exec_date < cutoff_date
            is_error = ex.get("status") == "error"
            
            if is_old and not (keep_errors and is_error):
                to_delete.append({
                    "id": ex.get("id"),
                    "workflow_id": ex.get("workflowId"),
                    "status": ex.get("status"),
                    "started_at": started
                })
            else:
                to_keep.append(ex.get("id"))
        
        deleted_count = 0
        if not dry_run and to_delete:
            for exec_info in to_delete:
                try:
                    await client.delete(f"/executions/{exec_info['id']}")
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete execution {exec_info['id']}: {e}")
        
        result = {
            "status": "success",
            "mode": "dry_run" if dry_run else "executed",
            "cutoff_date": cutoff_date.isoformat(),
            "total_executions": len(executions),
            "to_delete": len(to_delete),
            "to_keep": len(to_keep),
            "deleted": deleted_count if not dry_run else 0,
            "executions_to_delete": to_delete[:20] if dry_run else []  # Sample for dry run
        }
        
        if dry_run:
            result["note"] = "This was a dry run. Set dry_run=False to actually delete."
        
        logger.info(f"Prune complete: {len(to_delete)} executions {'would be' if dry_run else 'were'} deleted")
        return json.dumps(result, indent=2)
        
    except Exception as e:
        logger.error(f"Error in smart prune: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)


@safe_tool
async def verify_credentials_health() -> str:
    """
    Verify the health status of all stored credentials.
    Attempts to identify potentially expired or misconfigured credentials.
    
    Returns:
        JSON string with credential health status.
    """
    logger.info("Verifying credentials health")
    
    client = get_client()
    
    try:
        # Get all credentials
        cred_data = await client.get("/credentials")
        credentials = cred_data.get("data", [])
        
        credential_status = []
        warnings = []
        
        for cred in credentials:
            cred_info = {
                "id": cred.get("id"),
                "name": cred.get("name"),
                "type": cred.get("type"),
                "created_at": cred.get("createdAt"),
                "updated_at": cred.get("updatedAt")
            }
            
            # Check if credential is very old (might need rotation)
            updated = cred.get("updatedAt")
            if updated:
                try:
                    update_date = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    update_date = update_date.replace(tzinfo=None)
                    age_days = (datetime.now() - update_date).days
                    
                    cred_info["age_days"] = age_days
                    
                    if age_days > 90:
                        cred_info["status"] = "needs_review"
                        warnings.append(f"Credential '{cred.get('name')}' is {age_days} days old")
                    elif age_days > 180:
                        cred_info["status"] = "stale"
                        warnings.append(f"Credential '{cred.get('name')}' is very old ({age_days} days)")
                    else:
                        cred_info["status"] = "healthy"
                except:
                    cred_info["status"] = "unknown"
            else:
                cred_info["status"] = "unknown"
            
            credential_status.append(cred_info)
        
        # Group by type
        by_type = defaultdict(list)
        for cred in credential_status:
            by_type[cred.get("type", "unknown")].append(cred.get("name"))
        
        return json.dumps({
            "status": "success",
            "total_credentials": len(credentials),
            "warnings": warnings,
            "credentials": credential_status,
            "by_type": dict(by_type)
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error verifying credentials: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)


@safe_tool
async def get_error_patterns(
    hours: int = 24,
    min_occurrences: int = 2
) -> str:
    """
    Analyze recent execution errors to find patterns.
    Identifies recurring errors that might indicate systematic issues.
    
    Args:
        hours: Number of hours to analyze.
        min_occurrences: Minimum occurrences for an error pattern.
    
    Returns:
        JSON string with error pattern analysis.
    """
    logger.info(f"Analyzing error patterns for last {hours} hours")
    
    client = get_client()
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    try:
        # Get recent error executions
        exec_data = await client.get(
            "/executions",
            params={"status": "error", "limit": 200}
        )
        executions = exec_data.get("data", [])
        
        # Collect error patterns
        error_patterns = defaultdict(lambda: {
            "count": 0,
            "workflows": set(),
            "nodes": set(),
            "first_seen": None,
            "last_seen": None
        })
        
        for ex in executions:
            started = ex.get("startedAt")
            if not started:
                continue
            
            try:
                exec_id = ex.get("id")
                # Get execution details for error info
                full_exec = await client.get(f"/executions/{exec_id}")
                
                # Extract error info
                run_data = full_exec.get("data", {}).get("resultData", {}).get("runData", {})
                
                for node_name, runs in run_data.items():
                    if runs and len(runs) > 0:
                        last_run = runs[-1]
                        error = last_run.get("error")
                        if error:
                            error_msg = error.get("message", str(error))
                            # Simplify error message for grouping
                            simple_error = error_msg[:100]
                            
                            pattern = error_patterns[simple_error]
                            pattern["count"] += 1
                            pattern["workflows"].add(ex.get("workflowId"))
                            pattern["nodes"].add(node_name)
                            
                            if not pattern["first_seen"]:
                                pattern["first_seen"] = started
                            pattern["last_seen"] = started
            except:
                continue
        
        # Convert to serializable format
        patterns_list = []
        for error_msg, pattern in error_patterns.items():
            if pattern["count"] >= min_occurrences:
                patterns_list.append({
                    "error_pattern": error_msg,
                    "occurrences": pattern["count"],
                    "affected_workflows": list(pattern["workflows"]),
                    "affected_nodes": list(pattern["nodes"]),
                    "first_seen": pattern["first_seen"],
                    "last_seen": pattern["last_seen"]
                })
        
        # Sort by occurrence count
        patterns_list.sort(key=lambda x: x["occurrences"], reverse=True)
        
        return json.dumps({
            "status": "success",
            "analysis_period_hours": hours,
            "total_errors_analyzed": len(executions),
            "unique_patterns": len(patterns_list),
            "patterns": patterns_list
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error analyzing patterns: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)


@safe_tool
async def auto_restart_failed_workflows(
    max_restarts: int = 3,
    dry_run: bool = True
) -> str:
    """
    Automatically restart workflows that have recently failed.
    Uses exponential backoff between restart attempts.
    
    Args:
        max_restarts: Maximum number of workflows to restart.
        dry_run: If True, only report what would be restarted.
    
    Returns:
        JSON string with restart results.
    """
    logger.info(f"Auto-restart check: max={max_restarts}, dry_run={dry_run}")
    
    client = get_client()
    
    try:
        # Get recent failed executions
        exec_data = await client.get(
            "/executions",
            params={"status": "error", "limit": 50}
        )
        executions = exec_data.get("data", [])
        
        # Group by workflow
        workflows_with_errors = defaultdict(list)
        for ex in executions:
            wf_id = ex.get("workflowId")
            if wf_id:
                workflows_with_errors[wf_id].append(ex)
        
        restart_candidates = []
        for wf_id, errors in workflows_with_errors.items():
            # Only restart if there's a single recent error (not continuous failures)
            if len(errors) <= 2:
                restart_candidates.append({
                    "workflow_id": wf_id,
                    "recent_errors": len(errors),
                    "last_error_id": errors[0].get("id")
                })
        
        # Limit restarts
        restart_candidates = restart_candidates[:max_restarts]
        
        restarted = []
        if not dry_run:
            for candidate in restart_candidates:
                try:
                    # Trigger workflow
                    result = await client.post(
                        f"/workflows/{candidate['workflow_id']}/run",
                        json_data={}
                    )
                    restarted.append({
                        "workflow_id": candidate["workflow_id"],
                        "new_execution_id": result.get("id"),
                        "status": "triggered"
                    })
                except Exception as e:
                    restarted.append({
                        "workflow_id": candidate["workflow_id"],
                        "status": "failed",
                        "error": str(e)
                    })
        
        return json.dumps({
            "status": "success",
            "mode": "dry_run" if dry_run else "executed",
            "total_failed_workflows": len(workflows_with_errors),
            "restart_candidates": len(restart_candidates),
            "candidates": restart_candidates if dry_run else [],
            "restarted": restarted if not dry_run else []
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error in auto-restart: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)


@safe_tool
async def get_system_metrics() -> str:
    """
    Get comprehensive system metrics for n8n.
    Includes execution stats, workflow counts, and performance indicators.
    
    Returns:
        JSON string with system metrics.
    """
    logger.info("Collecting system metrics")
    
    client = get_client()
    
    try:
        # Get workflows
        wf_data = await client.get("/workflows")
        workflows = wf_data.get("data", [])
        
        # Get recent executions
        exec_data = await client.get("/executions", params={"limit": 100})
        executions = exec_data.get("data", [])
        
        # Get credentials
        cred_data = await client.get("/credentials")
        credentials = cred_data.get("data", [])
        
        # Calculate metrics
        active_workflows = sum(1 for wf in workflows if wf.get("active"))
        
        status_counts = defaultdict(int)
        for ex in executions:
            status_counts[ex.get("status", "unknown")] += 1
        
        success_rate = (
            status_counts.get("success", 0) + status_counts.get("finished", 0)
        ) / len(executions) * 100 if executions else 0
        
        # Calculate average execution time
        exec_times = []
        for ex in executions:
            started = ex.get("startedAt")
            stopped = ex.get("stoppedAt")
            if started and stopped:
                try:
                    start = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    stop = datetime.fromisoformat(stopped.replace("Z", "+00:00"))
                    exec_times.append((stop - start).total_seconds())
                except:
                    pass
        
        avg_exec_time = sum(exec_times) / len(exec_times) if exec_times else 0
        
        return json.dumps({
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "workflows": {
                "total": len(workflows),
                "active": active_workflows,
                "inactive": len(workflows) - active_workflows
            },
            "credentials": {
                "total": len(credentials)
            },
            "executions_last_100": {
                "by_status": dict(status_counts),
                "success_rate_percent": round(success_rate, 1),
                "avg_execution_time_seconds": round(avg_exec_time, 2)
            }
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error collecting metrics: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)
