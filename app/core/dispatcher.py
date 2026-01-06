"""
Quantum Core Dispatcher
Internal registry and router for all n8n and Docker skills.
Reduces visible tool count by mapping dynamic requests to service functions.
"""
import json
import asyncio
from typing import Dict, Any, Callable, Optional
from app.core.logging import gateway_logger as logger

# Management
from app.services.manager import list_all_workflows, toggle_workflow_state, delete_workflow, get_workflow_tags
# Architect
from app.services.architect import read_workflow_structure, deploy_workflow, clone_workflow
# Debugger
from app.services.debugger import diagnose_execution, analyze_execution_failures, get_execution_history
# Packages
from app.services.packages import install_community_node, uninstall_community_node, list_installed_nodes, get_n8n_info
# Credentials
from app.services.credentials import create_credential, list_credentials, get_credential_schema
# God Level n8n services
from app.services.live_surgery import get_waiting_executions, trigger_workflow_now, inject_execution_data, rerun_node_with_patch, get_execution_data, retry_failed_execution
from app.services.cicd import create_workflow_snapshot, list_workflow_snapshots, restore_workflow_from_snapshot, sync_workflows_to_git, import_workflow_from_git, workflow_unit_test, shadow_test_workflow, compare_workflow_versions
from app.services.autohealing import health_check_all, smart_db_prune, verify_credentials_health, get_error_patterns, auto_restart_failed_workflows, get_system_metrics
from app.services.semantic import explain_workflow_impact, generate_workflow_diagram, semantic_search_workflows, map_data_flow, identify_bottlenecks
from app.services.precognition import traffic_anomaly_detection, token_burn_rate_prediction, predict_failures, compute_reliability_score, detect_silence_anomaly
from app.services.evolution import ab_test_workflow, compare_workflow_performance, suggest_optimizations, workflow_complexity_analysis
from app.services.security import security_audit_workflow, scan_for_pii, emergency_deactivate_all, check_credential_usage
from app.services.node_factory import scaffold_custom_node, build_custom_node, list_custom_nodes, get_node_template
from app.services.orchestration import workflow_lint, generate_documentation, export_all_documentation, get_workflow_dependencies

# Docker services
from app.services.docker import (
    list_docker_containers, get_container_logs, diagnose_container_errors, get_container_stats, 
    restart_container, analyze_all_container_errors, get_container_inspect, list_container_files, 
    read_container_file, run_container_command, run_sql_in_container, prune_docker_images, 
    check_container_connection, inspect_container_dns, audit_image_freshness, backup_volume_to_host, 
    grep_log_across_containers, scan_container_security, recommend_resource_limits, 
    create_container_snapshot, check_port_availability, restore_volume_from_host, 
    find_newer_image_tags, add_compose_service_dependency, summarize_log_patterns
)

# Registry Mapping
REGISTRY = {
    # n8n Core
    "list_workflows": list_all_workflows,
    "toggle_workflow": toggle_workflow_state,
    "delete_workflow": delete_workflow,
    "get_workflow_tags": get_workflow_tags,
    "read_workflow": read_workflow_structure,
    "deploy_workflow": deploy_workflow,
    "clone_workflow": clone_workflow,
    "diagnose_execution": diagnose_execution,
    "analyze_failures": analyze_execution_failures,
    "get_execution_history": get_execution_history,
    "install_community_node": install_community_node,
    "uninstall_community_node": uninstall_community_node,
    "list_installed_nodes": list_installed_nodes,
    "get_info": get_n8n_info,
    "create_credential": create_credential,
    "list_credentials": list_credentials,
    "get_credential_schema": get_credential_schema,
    
    # God Level n8n
    "get_waiting_executions": get_waiting_executions,
    "trigger_now": trigger_workflow_now,
    "inject_execution_data": inject_execution_data,
    "rerun_with_patch": rerun_node_with_patch,
    "get_execution_data": get_execution_data,
    "retry_failed_execution": retry_failed_execution,
    "create_workflow_snapshot": create_workflow_snapshot,
    "list_snapshots": list_workflow_snapshots,
    "restore_snapshot": restore_workflow_from_snapshot,
    "sync_to_git": sync_workflows_to_git,
    "import_from_git": import_workflow_from_git,
    "unit_test": workflow_unit_test,
    "shadow_test": shadow_test_workflow,
    "compare_versions": compare_workflow_versions,
    "health_check_all": health_check_all,
    "prune_history": smart_db_prune,
    "verify_credentials": verify_credentials_health,
    "get_error_patterns": get_error_patterns,
    "auto_restart_failed": auto_restart_failed_workflows,
    "get_system_metrics": get_system_metrics,
    "explain_impact": explain_workflow_impact,
    "generate_diagram": generate_workflow_diagram,
    "semantic_search": semantic_search_workflows,
    "map_data_flow": map_data_flow,
    "identify_bottlenecks": identify_bottlenecks,
    "detect_anomaly": traffic_anomaly_detection,
    "predict_burn_rate": token_burn_rate_prediction,
    "predict_failures": predict_failures,
    "compute_reliability": compute_reliability_score,
    "detect_silence": detect_silence_anomaly,
    "ab_test_workflow": ab_test_workflow,
    "compare_performance": compare_workflow_performance,
    "suggest_optimizations": suggest_optimizations,
    "analyze_complexity": workflow_complexity_analysis,
    "security_audit": security_audit_workflow,
    "scan_pii": scan_for_pii,
    "kill_switch": emergency_deactivate_all,
    "check_credential_usage": check_credential_usage,
    "scaffold_node": scaffold_custom_node,
    "build_node": build_custom_node,
    "list_custom_nodes": list_custom_nodes,
    "get_node_template": get_node_template,
    "lint_workflow": workflow_lint,
    "generate_docs": generate_documentation,
    "export_docs": export_all_documentation,
    "get_dependencies": get_workflow_dependencies,

    # Docker
    "list_containers": list_docker_containers,
    "get_logs": get_container_logs,
    "diagnose_container_errors": diagnose_container_errors,
    "get_stats": get_container_stats,
    "restart_container": restart_container,
    "analyze_all_errors": analyze_all_container_errors,
    "inspect_container": get_container_inspect,
    "list_files": list_container_files,
    "read_file": read_container_file,
    "run_command": run_container_command,
    "run_sql": run_sql_in_container,
    "prune_images": prune_docker_images,
    "check_connectivity": check_container_connection,
    "inspect_dns": inspect_container_dns,
    "audit_freshness": audit_image_freshness,
    "backup_volume": backup_volume_to_host,
    "grep_logs": grep_log_across_containers,
    "scan_security": scan_container_security,
    "recommend_limits": recommend_resource_limits,
    "create_container_snapshot": create_container_snapshot,
    "check_port": check_port_availability,
    "restore_volume": restore_volume_from_host,
    "find_tags": find_newer_image_tags,
    "add_dependency": add_compose_service_dependency,
    "summarize_log_patterns": summarize_log_patterns
}

async def dispatch(category: str, skill: str, params: Dict[str, Any]) -> str:
    """Routes a skill request to the service layer."""
    if skill not in REGISTRY:
        return json.dumps({
            "status": "error",
            "message": f"Skill '{skill}' not found in registry.",
            "available_skills": list(REGISTRY.keys())
        })
    
    func = REGISTRY[skill]
    try:
        # Most of these are async, but some might be sync wrappers
        if asyncio.iscoroutinefunction(func):
            return await func(**params)
        else:
            return func(**params)
    except Exception as e:
        logger.error(f"Dispatch error for {skill}: {e}")
        return json.dumps({"status": "error", "message": str(e)})

def get_skill_manifest(category_filter: Optional[str] = None) -> Dict[str, Any]:
    """Returns the list of all available skills for the AI to discover."""
    # In a more advanced version, we could group by category here
    return {
        "total": len(REGISTRY),
        "skills": list(REGISTRY.keys())
    }
