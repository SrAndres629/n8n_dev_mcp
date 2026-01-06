"""
Quantum Core Gateway - Senior Advanced Edition
Exposes < 15 Semantic Kernels for High-Fidelity Orchestration.
"""
import json
from contextlib import asynccontextmanager
from typing import Dict, Any, List

from fastapi import FastAPI, Request
from fastmcp import FastMCP

from app.core.config import settings
from app.core.client import get_client, safe_tool
from app.core.logging import gateway_logger as logger
from app.core.dispatcher import dispatch, get_skill_manifest

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("⚡ Expert Kernel Gateway Starting")
    logger.info("=" * 60)
    yield
    client = get_client()
    await client.close()
    logger.info("👋 Expert Kernel Shutdown")

mcp = FastMCP("n8n Architect")

# --- KERNEL EXPERTS ---

@mcp.tool(name="kernel_workflow_architect")
@safe_tool
async def workflow_architect_expert(skill_name: str, parameters: Dict[str, Any]) -> str:
    """
    Expert for the entire n8n workflow lifecycle (Architecture & CI/CD).
    Handles: deploy, clone, read, snapshots, git_sync, unit_test, compare_versions.
    Abstracts semantic structure and version stability.
    """
    return await dispatch("n8n", skill_name, parameters)

@mcp.tool(name="kernel_operational_surgeon")
@safe_tool
async def operational_surgeon_expert(skill_name: str, parameters: Dict[str, Any]) -> str:
    """
    Expert for live state manipulation and auto-healing.
    Handles: live surgery (inject data, retry, patch), execution diagnosis, 
    and auto-restarts. Manages the 'living' state of the engine.
    """
    return await dispatch("n8n", skill_name, parameters)

@mcp.tool(name="kernel_system_oracle")
@safe_tool
async def system_oracle_expert(skill_name: str, parameters: Dict[str, Any]) -> str:
    """
    Predictive and Analytical Expert for system health.
    Handles: Metrics, Anomaly detection, Failure predictions, War Room reports.
    Provides mathematical certainty on system reliability and burn rates.
    """
    return await dispatch("n8n", skill_name, parameters)

@mcp.tool(name="kernel_infrastructure_guardian")
@safe_tool
async def infrastructure_guardian_expert(skill_name: str, parameters: Dict[str, Any]) -> str:
    """
    Expert for Docker infrastructure and security.
    Handles: Container lifecycle, Log analysis, Security audits, Resource optimization, 
    Network connectivity, and Volume management.
    """
    return await dispatch("docker", skill_name, parameters)

@mcp.tool(name="kernel_semantic_intelligence")
@safe_tool
async def semantic_intelligence_expert(skill_name: str, parameters: Dict[str, Any]) -> str:
    """
    Expert for documentation, impact analysis and data flow mapping.
    Handles: Diagrams, Documentation indexing, Impact analysis, Semantic search.
    Abstracts the logic relationships between isolated components.
    """
    return await dispatch("n8n", skill_name, parameters)

@mcp.tool(name="kernel_asset_factory")
@safe_tool
async def asset_factory_expert(skill_name: str, parameters: Dict[str, Any]) -> str:
    """
    Expert for creating and managing custom nodes and credentials.
    Handles: Node scaffolding, Building, Templates, and Credential management.
    """
    return await dispatch("n8n", skill_name, parameters)

@mcp.tool(name="list_expert_skills")
async def list_expert_skills_tool() -> str:
    """Discovers all internal skills available within the Kernels."""
    return json.dumps(get_skill_manifest(), indent=2)

# --- God Mode Protocol (High Visibility) ---
from app.services.god_protocol import system_war_room_report, protocol_execute_sdlc, shadow_simulation_patch
mcp.tool(name="system_war_room_report")(system_war_room_report)
mcp.tool(name="protocol_execute_sdlc")(protocol_execute_sdlc)
mcp.tool(name="shadow_simulation_patch")(shadow_simulation_patch)


# =============================================================================
# FASTAPI APP
# =============================================================================
app = FastAPI(title="n8n Architect (Expert Kernels)", lifespan=lifespan)

@app.get("/sse")
async def handle_sse(request: Request): return await mcp.sse_handler(request)
@app.post("/sse")
async def handle_sse_post(request: Request): return await mcp.sse_handler(request)

@app.get("/health")
async def health(): return {"status": "healthy", "mode": "expert_kernels", "skills": len(get_skill_manifest()["skills"])}

if __name__ == "__main__":
    mcp.run()
