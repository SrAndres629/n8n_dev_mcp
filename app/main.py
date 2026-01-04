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
from app.services.credentials import create_credential, list_credentials, get_credential_schema

# Import God Level service modules
from app.services.live_surgery import (
    get_waiting_executions,
    trigger_workflow_now,
    inject_execution_data,
    rerun_node_with_patch,
    get_execution_data,
    retry_failed_execution
)
from app.services.cicd import (
    create_workflow_snapshot,
    list_workflow_snapshots,
    restore_workflow_from_snapshot,
    sync_workflows_to_git,
    import_workflow_from_git,
    workflow_unit_test,
    shadow_test_workflow,
    compare_workflow_versions
)
from app.services.autohealing import (
    health_check_all,
    smart_db_prune,
    verify_credentials_health,
    get_error_patterns,
    auto_restart_failed_workflows,
    get_system_metrics
)
from app.services.semantic import (
    explain_workflow_impact,
    generate_workflow_diagram,
    semantic_search_workflows,
    map_data_flow,
    identify_bottlenecks
)
from app.services.precognition import (
    traffic_anomaly_detection,
    token_burn_rate_prediction,
    predict_failures,
    compute_reliability_score,
    detect_silence_anomaly
)
from app.services.evolution import (
    ab_test_workflow,
    compare_workflow_performance,
    suggest_optimizations,
    workflow_complexity_analysis
)
from app.services.security import (
    security_audit_workflow,
    scan_for_pii,
    emergency_deactivate_all,
    check_credential_usage
)
from app.services.node_factory import (
    scaffold_custom_node,
    build_custom_node,
    list_custom_nodes,
    get_node_template
)
from app.services.orchestration import (
    workflow_lint,
    generate_documentation,
    export_all_documentation,
    get_workflow_dependencies
)

from app.services.docker import (
    list_docker_containers,
    get_container_logs,
    diagnose_container_errors,
    get_container_stats,
    restart_container,
    analyze_all_container_errors,
    analyze_all_container_errors,
    get_container_inspect,
    list_container_files,
    read_container_file,
    run_container_command,
    run_sql_in_container,
    prune_docker_images,
    check_container_connection,
    inspect_container_dns,
    audit_image_freshness,
    audit_image_freshness,
    backup_volume_to_host,
    grep_log_across_containers,
    scan_container_security,
    recommend_resource_limits,
    create_container_snapshot,
    check_port_availability,
    restore_volume_from_host,
    find_newer_image_tags,
    add_compose_service_dependency,
    summarize_log_patterns
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
# FASTMCP SERVER INITIALIZATION
# =============================================================================
mcp = FastMCP("n8n Architect")

if settings.enable_n8n_tools:
    # --- Register Management Tools ---
    mcp.tool(name="n8n_list_workflows")(list_all_workflows)
    mcp.tool(name="n8n_toggle_workflow")(toggle_workflow_state)
    mcp.tool(name="n8n_delete_workflow")(delete_workflow)
    mcp.tool(name="n8n_get_workflow_tags")(get_workflow_tags)

    # --- Register Architecture Tools ---
    mcp.tool(name="n8n_read_workflow")(read_workflow_structure)
    mcp.tool(name="n8n_deploy_workflow")(deploy_workflow)
    mcp.tool(name="n8n_clone_workflow")(clone_workflow)

    # --- Register Debugging Tools ---
    mcp.tool(name="n8n_diagnose_execution")(diagnose_execution)
    mcp.tool(name="n8n_analyze_failures")(analyze_execution_failures)
    mcp.tool(name="n8n_get_execution_history")(get_execution_history)

    # --- Register Package Management Tools ---
    mcp.tool(name="n8n_install_community_node")(install_community_node)
    mcp.tool(name="n8n_uninstall_community_node")(uninstall_community_node)
    mcp.tool(name="n8n_list_installed_nodes")(list_installed_nodes)
    mcp.tool(name="n8n_get_info")(get_n8n_info)

    # --- Register Credential Tools ---
    mcp.tool(name="n8n_create_credential")(create_credential)
    mcp.tool(name="n8n_list_credentials")(list_credentials)
    mcp.tool(name="n8n_get_credential_schema")(get_credential_schema)

if settings.enable_docker_tools:
    # --- Register Docker Debugging Tools ---
    mcp.tool(name="docker_list_containers")(list_docker_containers)
    mcp.tool(name="docker_get_logs")(get_container_logs)
    mcp.tool(name="docker_diagnose_errors")(diagnose_container_errors)
    mcp.tool(name="docker_get_stats")(get_container_stats)
    mcp.tool(name="docker_restart_container")(restart_container)
    mcp.tool(name="docker_analyze_all_errors")(analyze_all_container_errors)
    mcp.tool(name="docker_inspect_container")(get_container_inspect)

    # --- Register God Level Docker Tools ---
    mcp.tool(name="docker_list_files")(list_container_files)
    mcp.tool(name="docker_read_file")(read_container_file)
    mcp.tool(name="docker_run_command")(run_container_command)
    mcp.tool(name="docker_run_sql")(run_sql_in_container)
    mcp.tool(name="docker_prune_images")(prune_docker_images)
    mcp.tool(name="docker_check_connectivity")(check_container_connection)
    mcp.tool(name="docker_inspect_dns")(inspect_container_dns)
    mcp.tool(name="docker_audit_freshness")(audit_image_freshness)
    mcp.tool(name="docker_backup_volume")(backup_volume_to_host)
    mcp.tool(name="docker_grep_logs")(grep_log_across_containers)
    mcp.tool(name="docker_scan_security")(scan_container_security)
    mcp.tool(name="docker_recommend_limits")(recommend_resource_limits)
    mcp.tool(name="docker_create_snapshot")(create_container_snapshot)
    mcp.tool(name="docker_check_port")(check_port_availability)
    mcp.tool(name="docker_restore_volume")(restore_volume_from_host)
    mcp.tool(name="docker_find_tags")(find_newer_image_tags)
    mcp.tool(name="docker_add_dependency")(add_compose_service_dependency)
    mcp.tool(name="docker_summarize_log_patterns")(summarize_log_patterns)


# =============================================================================
# GOD LEVEL TOOLS REGISTRATION
# =============================================================================

if settings.enable_n8n_tools:
    # --- Live State Surgery Tools ---
    mcp.tool(name="n8n_get_waiting_executions")(get_waiting_executions)
    mcp.tool(name="n8n_trigger_now")(trigger_workflow_now)
    mcp.tool(name="n8n_inject_execution_data")(inject_execution_data)
    mcp.tool(name="n8n_rerun_with_patch")(rerun_node_with_patch)
    mcp.tool(name="n8n_get_execution_data")(get_execution_data)
    mcp.tool(name="n8n_retry_failed_execution")(retry_failed_execution)

    # --- CI/CD & Version Control Tools ---
    mcp.tool(name="n8n_create_snapshot")(create_workflow_snapshot)
    mcp.tool(name="n8n_list_snapshots")(list_workflow_snapshots)
    mcp.tool(name="n8n_restore_snapshot")(restore_workflow_from_snapshot)
    mcp.tool(name="n8n_sync_to_git")(sync_workflows_to_git)
    mcp.tool(name="n8n_import_from_git")(import_workflow_from_git)
    mcp.tool(name="n8n_unit_test")(workflow_unit_test)
    mcp.tool(name="n8n_shadow_test")(shadow_test_workflow)
    mcp.tool(name="n8n_compare_versions")(compare_workflow_versions)

    # --- Auto-Healing Tools ---
    mcp.tool(name="n8n_health_check_all")(health_check_all)
    mcp.tool(name="n8n_prune_history")(smart_db_prune)
    mcp.tool(name="n8n_verify_credentials")(verify_credentials_health)
    mcp.tool(name="n8n_get_error_patterns")(get_error_patterns)
    mcp.tool(name="n8n_auto_restart_failed")(auto_restart_failed_workflows)
    mcp.tool(name="n8n_get_system_metrics")(get_system_metrics)

    # --- Semantic Intelligence Tools ---
    mcp.tool(name="n8n_explain_impact")(explain_workflow_impact)
    mcp.tool(name="n8n_generate_diagram")(generate_workflow_diagram)
    mcp.tool(name="n8n_semantic_search")(semantic_search_workflows)
    mcp.tool(name="n8n_map_data_flow")(map_data_flow)
    mcp.tool(name="n8n_identify_bottlenecks")(identify_bottlenecks)

    # --- Precognition Tools ---
    mcp.tool(name="n8n_detect_anomaly")(traffic_anomaly_detection)
    mcp.tool(name="n8n_predict_burn_rate")(token_burn_rate_prediction)
    mcp.tool(name="n8n_predict_failures")(predict_failures)
    mcp.tool(name="n8n_compute_reliability")(compute_reliability_score)
    mcp.tool(name="n8n_detect_silence")(detect_silence_anomaly)

    # --- Evolution Engine Tools ---
    mcp.tool(name="n8n_ab_test_workflow")(ab_test_workflow)
    mcp.tool(name="n8n_compare_performance")(compare_workflow_performance)
    mcp.tool(name="n8n_suggest_optimizations")(suggest_optimizations)
    mcp.tool(name="n8n_analyze_complexity")(workflow_complexity_analysis)

    # --- Security Tools ---
    mcp.tool(name="n8n_security_audit")(security_audit_workflow)
    mcp.tool(name="n8n_scan_pii")(scan_for_pii)
    mcp.tool(name="n8n_kill_switch")(emergency_deactivate_all)
    mcp.tool(name="n8n_check_credential_usage")(check_credential_usage)

    # --- Custom Node Factory Tools ---
    mcp.tool(name="n8n_scaffold_node")(scaffold_custom_node)
    mcp.tool(name="n8n_build_node")(build_custom_node)
    mcp.tool(name="n8n_list_custom_nodes")(list_custom_nodes)
    mcp.tool(name="n8n_get_node_template")(get_node_template)

    # --- Orchestration Tools ---
    mcp.tool(name="n8n_lint_workflow")(workflow_lint)
    mcp.tool(name="n8n_generate_docs")(generate_documentation)
    mcp.tool(name="n8n_export_docs")(export_all_documentation)
    mcp.tool(name="n8n_get_dependencies")(get_workflow_dependencies)



# =============================================================================
# COMPOSITE TOOLS (High-Level Operations)
# =============================================================================
@mcp.tool(name="n8n_auto_fix_workflow")
@safe_tool
async def auto_fix_workflow_tool(
    execution_id: str,
    fixed_nodes: Union[str, List[Dict[str, Any]]],
    fixed_connections: Union[str, Dict[str, Any], None] = None
) -> str:
    """
    Auto-fix a failing workflow: diagnose the error, then apply a patch.
    """
    # Renamed local function to avoid conflict with registration name if needed
    # but actual logic stays same
    return await auto_fix_workflow(execution_id, fixed_nodes, fixed_connections)


@mcp.tool(name="n8n_create_workflow")
@safe_tool
async def create_new_workflow_tool(
    name: str,
    nodes_json: str,
    connections_json: str,
    activate: bool = False
) -> str:
    """
    Create a new workflow from JSON strings.
    """
    return await deploy_workflow(
        name=name,
        nodes=nodes_json,
        connections=connections_json,
        activate=activate
    )


@mcp.tool(name="n8n_install_external_node")
@safe_tool
async def install_ext_node_tool(package_name: str) -> str:
    """
    Install an external/community node from npm.
    """
    return await install_community_node(package_name)



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
# MCP MOUNTING (The Critical Fix)
# =============================================================================
try:
    # Attempt to mount using fastmcp internal method if available
    # This exposes the SSE endpoint at /sse/sse (standard pattern)
    # or /sse depending on implementation
    if hasattr(mcp, "mount_sse_server"):
        mcp.mount_sse_server(app, "/sse")
    else:
        # Fallback manual mounting
        logger.info("Using manual SSE handler mounting")
        @app.get("/sse")
        async def handle_sse(request: Request):
            return await mcp.sse_handler(request)
            
        @app.post("/sse")
        async def handle_sse_post(request: Request):
            return await mcp.sse_handler(request)
            
except Exception as e:
    logger.error(f"Failed to mount MCP SSE server: {e}")
    # Last resort fallback
    @app.get("/sse")
    async def handle_sse_fallback(request: Request):
        return await mcp.sse_handler(request)


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


def get_mcp() -> FastMCP:
    """Get the FastMCP server instance."""
    return mcp

def get_app() -> FastAPI:
    """Get the FastAPI app instance."""
    return app

if __name__ == "__main__":
    mcp.run()
