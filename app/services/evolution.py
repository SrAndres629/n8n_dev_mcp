"""
Evolution Engine Service - A/B Testing & Optimization
Provides workflow optimization, benchmarking, and refactoring capabilities.
"""
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from collections import defaultdict

from app.core.client import get_client, safe_tool
from app.core.logging import gateway_logger as logger


@safe_tool
async def ab_test_workflow(workflow_id: str, variant_name: str = "Variant_B") -> str:
    """Create a variant of a workflow for A/B testing."""
    logger.info(f"Creating A/B test variant for: {workflow_id}")
    client = get_client()
    
    try:
        original = await client.get(f"/workflows/{workflow_id}")
        original_name = original.get("name", "Unknown")
        
        variant_payload = {
            "name": f"{original_name} [{variant_name}]",
            "nodes": original.get("nodes", []),
            "connections": original.get("connections", {}),
            "settings": original.get("settings", {})
        }
        
        result = await client.post("/workflows", json_data=variant_payload)
        
        return json.dumps({
            "status": "success",
            "original_id": workflow_id,
            "variant_id": result.get("id"),
            "variant_name": variant_payload["name"],
            "instructions": "Modify the variant, activate both, and compare performance"
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def compare_workflow_performance(workflow_a_id: str, workflow_b_id: str) -> str:
    """Compare execution performance between two workflows."""
    logger.info(f"Comparing performance: {workflow_a_id} vs {workflow_b_id}")
    client = get_client()
    
    try:
        # Get executions for both
        exec_a = await client.get("/executions", params={"workflowId": workflow_a_id, "limit": 50})
        exec_b = await client.get("/executions", params={"workflowId": workflow_b_id, "limit": 50})
        
        def analyze_executions(executions):
            data = executions.get("data", [])
            success = sum(1 for e in data if e.get("status") in ["success", "finished"])
            errors = sum(1 for e in data if e.get("status") == "error")
            
            times = []
            for e in data:
                started = e.get("startedAt")
                stopped = e.get("stoppedAt")
                if started and stopped:
                    try:
                        s = datetime.fromisoformat(started.replace("Z", "+00:00"))
                        t = datetime.fromisoformat(stopped.replace("Z", "+00:00"))
                        times.append((t - s).total_seconds())
                    except:
                        pass
            
            return {
                "total": len(data),
                "success": success,
                "errors": errors,
                "success_rate": round(success/len(data)*100, 1) if data else 0,
                "avg_time_seconds": round(sum(times)/len(times), 2) if times else 0
            }
        
        stats_a = analyze_executions(exec_a)
        stats_b = analyze_executions(exec_b)
        
        winner = None
        if stats_a["success_rate"] > stats_b["success_rate"]:
            winner = workflow_a_id
        elif stats_b["success_rate"] > stats_a["success_rate"]:
            winner = workflow_b_id
        
        return json.dumps({
            "status": "success",
            "workflow_a": {"id": workflow_a_id, **stats_a},
            "workflow_b": {"id": workflow_b_id, **stats_b},
            "winner": winner,
            "recommendation": f"Workflow {winner} performs better" if winner else "No clear winner"
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def suggest_optimizations(workflow_id: str) -> str:
    """Analyze a workflow and suggest optimizations."""
    logger.info(f"Analyzing optimizations for: {workflow_id}")
    client = get_client()
    
    try:
        workflow = await client.get(f"/workflows/{workflow_id}")
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        suggestions = []
        
        # Check for common issues
        http_nodes = [n for n in nodes if "http" in n.get("type", "").lower()]
        if len(http_nodes) > 3:
            suggestions.append({
                "type": "performance",
                "issue": f"Multiple HTTP nodes ({len(http_nodes)})",
                "suggestion": "Consider batching requests or using a sub-workflow"
            })
        
        code_nodes = [n for n in nodes if "code" in n.get("type", "").lower()]
        for node in code_nodes:
            code = node.get("parameters", {}).get("jsCode", "")
            if "await" not in code and len(code) > 500:
                suggestions.append({
                    "type": "code_quality",
                    "node": node.get("name"),
                    "suggestion": "Consider using async/await for better performance"
                })
        
        if len(nodes) > 20:
            suggestions.append({
                "type": "complexity",
                "issue": f"High node count ({len(nodes)})",
                "suggestion": "Consider splitting into sub-workflows"
            })
        
        # Check for unused nodes (no connections)
        connected_nodes = set()
        for source, conns in connections.items():
            connected_nodes.add(source)
            for _, targets in conns.items():
                for t in targets:
                    for c in t:
                        connected_nodes.add(c.get("node"))
        
        orphan_nodes = [n.get("name") for n in nodes if n.get("name") not in connected_nodes and "trigger" not in n.get("type", "").lower()]
        if orphan_nodes:
            suggestions.append({
                "type": "cleanup",
                "issue": "Disconnected nodes found",
                "nodes": orphan_nodes,
                "suggestion": "Remove or connect these nodes"
            })
        
        return json.dumps({
            "status": "success",
            "workflow_id": workflow_id,
            "node_count": len(nodes),
            "suggestions_count": len(suggestions),
            "suggestions": suggestions
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def workflow_complexity_analysis(workflow_id: str) -> str:
    """Analyze the complexity of a workflow."""
    logger.info(f"Analyzing complexity: {workflow_id}")
    client = get_client()
    
    try:
        workflow = await client.get(f"/workflows/{workflow_id}")
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        # Count connection types
        total_connections = sum(
            len(t) for conns in connections.values() 
            for targets in conns.values() for t in targets
        )
        
        # Calculate cyclomatic complexity (branches)
        branches = sum(1 for n in nodes if any(x in n.get("type", "").lower() for x in ["if", "switch", "filter"]))
        
        # Count unique node types
        node_types = set(n.get("type", "") for n in nodes)
        
        # Complexity score
        score = len(nodes) + (branches * 2) + (total_connections * 0.5)
        complexity_level = "low" if score < 20 else "medium" if score < 50 else "high"
        
        return json.dumps({
            "status": "success",
            "workflow_id": workflow_id,
            "metrics": {
                "node_count": len(nodes),
                "connection_count": total_connections,
                "branch_count": branches,
                "unique_node_types": len(node_types)
            },
            "complexity_score": round(score, 1),
            "complexity_level": complexity_level
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
