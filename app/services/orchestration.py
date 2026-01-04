"""
Orchestration Service - Environment Management & Documentation
Handles workflow promotion, linting, and auto-documentation.
"""
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

from app.core.client import get_client, safe_tool
from app.core.config import settings
from app.core.logging import gateway_logger as logger


def _get_docs_dir() -> str:
    """Get documentation directory."""
    docs_dir = os.path.join(settings.n8n_data_dir, "workflow_docs")
    os.makedirs(docs_dir, exist_ok=True)
    return docs_dir


@safe_tool
async def workflow_lint(workflow_id: str) -> str:
    """Lint a workflow for common anti-patterns and issues."""
    logger.info(f"Linting workflow: {workflow_id}")
    client = get_client()
    
    try:
        workflow = await client.get(f"/workflows/{workflow_id}")
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        issues = []
        
        # Check naming conventions
        for node in nodes:
            name = node.get("name", "")
            if name.startswith("Copy of") or "1" in name[-2:]:
                issues.append({
                    "rule": "naming",
                    "node": name,
                    "message": "Consider using descriptive names",
                    "severity": "warning"
                })
        
        # Check for error handling
        has_error_handler = any(
            "error" in n.get("type", "").lower() or "errorTrigger" in n.get("type", "")
            for n in nodes
        )
        if not has_error_handler and len(nodes) > 3:
            issues.append({
                "rule": "error_handling",
                "message": "No error handling nodes found",
                "severity": "warning"
            })
        
        # Check for trigger
        has_trigger = any(
            "trigger" in n.get("type", "").lower() or "webhook" in n.get("type", "").lower()
            for n in nodes
        )
        if not has_trigger:
            issues.append({
                "rule": "trigger",
                "message": "No trigger node found - workflow won't run automatically",
                "severity": "error"
            })
        
        # Check node count
        if len(nodes) > 30:
            issues.append({
                "rule": "complexity",
                "message": f"High node count ({len(nodes)}). Consider sub-workflows",
                "severity": "warning"
            })
        
        # Check for dead-end nodes
        all_targets = set()
        for source, conns in connections.items():
            for _, targets in conns.items():
                for t in targets:
                    for c in t:
                        all_targets.add(c.get("node"))
        
        dead_ends = [n.get("name") for n in nodes 
                    if n.get("name") not in connections and n.get("name") in all_targets]
        
        passed = len([i for i in issues if i["severity"] == "error"]) == 0
        
        return json.dumps({
            "status": "success",
            "workflow_id": workflow_id,
            "passed": passed,
            "total_issues": len(issues),
            "errors": len([i for i in issues if i["severity"] == "error"]),
            "warnings": len([i for i in issues if i["severity"] == "warning"]),
            "issues": issues
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def generate_documentation(workflow_id: str) -> str:
    """Generate markdown documentation for a workflow."""
    logger.info(f"Generating docs for: {workflow_id}")
    client = get_client()
    
    try:
        workflow = await client.get(f"/workflows/{workflow_id}")
        name = workflow.get("name", "Unknown")
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        # Build documentation
        doc_lines = [
            f"# {name}",
            "",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**Workflow ID**: {workflow_id}",
            f"**Status**: {'Active' if workflow.get('active') else 'Inactive'}",
            "",
            "## Overview",
            "",
            f"This workflow contains **{len(nodes)} nodes** connected in sequence.",
            "",
            "## Nodes",
            ""
        ]
        
        # Document each node
        for node in nodes:
            node_name = node.get("name", "Unknown")
            node_type = node.get("type", "Unknown")
            doc_lines.append(f"### {node_name}")
            doc_lines.append(f"- **Type**: `{node_type}`")
            
            # Find connections
            outgoing = []
            if node_name in connections:
                for output_type, targets in connections[node_name].items():
                    for t in targets:
                        for c in t:
                            outgoing.append(c.get("node"))
            
            if outgoing:
                doc_lines.append(f"- **Outputs to**: {', '.join(outgoing)}")
            doc_lines.append("")
        
        # Data flow summary
        doc_lines.extend([
            "## Data Flow",
            "",
            "```mermaid",
            "graph LR"
        ])
        
        for source, conns in connections.items():
            safe_source = source.replace(" ", "_")[:20]
            for _, targets in conns.items():
                for t in targets:
                    for c in t:
                        target = c.get("node", "")
                        safe_target = target.replace(" ", "_")[:20]
                        doc_lines.append(f"    {safe_source} --> {safe_target}")
        
        doc_lines.append("```")
        
        doc_content = "\n".join(doc_lines)
        
        # Save to file
        docs_dir = _get_docs_dir()
        safe_name = "".join(c if c.isalnum() else "_" for c in name)
        doc_path = os.path.join(docs_dir, f"{safe_name}.md")
        
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(doc_content)
        
        return json.dumps({
            "status": "success",
            "workflow_id": workflow_id,
            "workflow_name": name,
            "doc_path": doc_path,
            "doc_preview": doc_content[:500] + "..."
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def export_all_documentation() -> str:
    """Generate documentation for all workflows."""
    logger.info("Generating docs for all workflows")
    client = get_client()
    
    try:
        wf_data = await client.get("/workflows")
        workflows = wf_data.get("data", [])
        
        docs_dir = _get_docs_dir()
        generated = []
        
        for wf in workflows:
            try:
                result = await generate_documentation(wf["id"])
                result_data = json.loads(result)
                if result_data.get("status") == "success":
                    generated.append({
                        "id": wf["id"],
                        "name": wf["name"],
                        "doc_path": result_data.get("doc_path")
                    })
            except:
                pass
        
        # Create index
        index_lines = [
            "# Workflow Documentation Index",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Workflows",
            ""
        ]
        
        for doc in generated:
            index_lines.append(f"- [{doc['name']}]({os.path.basename(doc['doc_path'])})")
        
        index_path = os.path.join(docs_dir, "INDEX.md")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("\n".join(index_lines))
        
        return json.dumps({
            "status": "success",
            "docs_directory": docs_dir,
            "workflows_documented": len(generated),
            "index_file": index_path
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def get_workflow_dependencies(workflow_id: str) -> str:
    """Analyze workflow dependencies (credentials, other workflows)."""
    logger.info(f"Analyzing dependencies for: {workflow_id}")
    client = get_client()
    
    try:
        workflow = await client.get(f"/workflows/{workflow_id}")
        nodes = workflow.get("nodes", [])
        
        credentials_used = set()
        sub_workflows = []
        external_services = set()
        
        for node in nodes:
            node_type = node.get("type", "").lower()
            params = node.get("parameters", {})
            credentials = node.get("credentials", {})
            
            # Track credentials
            for cred_type, cred_data in credentials.items():
                if isinstance(cred_data, dict):
                    cred_name = cred_data.get("name", cred_type)
                else:
                    cred_name = str(cred_data)
                credentials_used.add(f"{cred_type}: {cred_name}")
            
            # Track sub-workflows
            if "workflow" in node_type:
                wf_id = params.get("workflowId")
                if wf_id:
                    sub_workflows.append(wf_id)
            
            # Track external services
            if "http" in node_type:
                url = params.get("url", "")
                if url:
                    try:
                        from urllib.parse import urlparse
                        host = urlparse(url).netloc
                        if host:
                            external_services.add(host)
                    except:
                        pass
        
        return json.dumps({
            "status": "success",
            "workflow_id": workflow_id,
            "dependencies": {
                "credentials": list(credentials_used),
                "sub_workflows": sub_workflows,
                "external_services": list(external_services)
            },
            "total_credentials": len(credentials_used),
            "total_external_services": len(external_services)
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
