"""
Security Service - Data Protection & Access Control
Provides security scanning, data masking, and emergency controls.
"""
import json
import re
from typing import Dict, Any, Optional, List

from app.core.client import get_client, safe_tool
from app.core.logging import gateway_logger as logger

# PII patterns
PII_PATTERNS = {
    "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    "credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
    "ssn": r'\b\d{3}[-]?\d{2}[-]?\d{4}\b',
    "ip_address": r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
}


@safe_tool
async def security_audit_workflow(workflow_id: str) -> str:
    """Perform a security audit on a workflow."""
    logger.info(f"Security audit for: {workflow_id}")
    client = get_client()
    
    try:
        workflow = await client.get(f"/workflows/{workflow_id}")
        nodes = workflow.get("nodes", [])
        
        issues = []
        
        for node in nodes:
            name = node.get("name", "")
            node_type = node.get("type", "").lower()
            params = json.dumps(node.get("parameters", {}))
            
            # Check for hardcoded secrets
            secret_patterns = ["password", "secret", "api_key", "token", "apikey"]
            for pattern in secret_patterns:
                if pattern in params.lower() and "{{" not in params:
                    issues.append({
                        "severity": "high",
                        "node": name,
                        "issue": f"Potential hardcoded secret ({pattern})",
                        "recommendation": "Use credentials instead of hardcoded values"
                    })
            
            # Check for HTTP without HTTPS
            if "http" in node_type:
                url = node.get("parameters", {}).get("url", "")
                if url.startswith("http://") and "localhost" not in url:
                    issues.append({
                        "severity": "medium",
                        "node": name,
                        "issue": "Insecure HTTP connection",
                        "recommendation": "Use HTTPS for external connections"
                    })
            
            # Check for SQL injection risks
            if "postgres" in node_type or "mysql" in node_type:
                query = node.get("parameters", {}).get("query", "")
                if "{{" in query and "+" in query:
                    issues.append({
                        "severity": "high",
                        "node": name,
                        "issue": "Potential SQL injection vector",
                        "recommendation": "Use parameterized queries"
                    })
        
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        for issue in issues:
            severity_counts[issue["severity"]] += 1
        
        overall_risk = "critical" if severity_counts["high"] > 2 else \
                       "high" if severity_counts["high"] > 0 else \
                       "medium" if severity_counts["medium"] > 2 else "low"
        
        return json.dumps({
            "status": "success",
            "workflow_id": workflow_id,
            "overall_risk": overall_risk,
            "issue_counts": severity_counts,
            "issues": issues
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def scan_for_pii(workflow_id: str) -> str:
    """Scan a workflow for potential PII exposure."""
    logger.info(f"PII scan for: {workflow_id}")
    client = get_client()
    
    try:
        workflow = await client.get(f"/workflows/{workflow_id}")
        content = json.dumps(workflow)
        
        findings = []
        for pii_type, pattern in PII_PATTERNS.items():
            matches = re.findall(pattern, content)
            if matches:
                findings.append({
                    "type": pii_type,
                    "count": len(matches),
                    "sample": matches[0][:4] + "****" if matches else None
                })
        
        return json.dumps({
            "status": "success",
            "workflow_id": workflow_id,
            "pii_detected": len(findings) > 0,
            "findings": findings,
            "recommendation": "Review and mask sensitive data" if findings else "No PII detected"
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def emergency_deactivate_all(dry_run: bool = True) -> str:
    """Emergency: Deactivate all active workflows (kill switch)."""
    logger.info(f"Emergency deactivate: dry_run={dry_run}")
    client = get_client()
    
    try:
        wf_data = await client.get("/workflows")
        workflows = wf_data.get("data", [])
        
        active_workflows = [wf for wf in workflows if wf.get("active")]
        
        deactivated = []
        if not dry_run:
            for wf in active_workflows:
                try:
                    await client.post(f"/workflows/{wf['id']}/deactivate")
                    deactivated.append(wf["id"])
                except Exception as e:
                    logger.warning(f"Failed to deactivate {wf['id']}: {e}")
        
        return json.dumps({
            "status": "success",
            "mode": "dry_run" if dry_run else "executed",
            "active_workflows_found": len(active_workflows),
            "deactivated": len(deactivated) if not dry_run else 0,
            "workflow_ids": [wf["id"] for wf in active_workflows][:10],
            "warning": "⚠️ Use with caution - this stops all automation!"
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)


@safe_tool
async def check_credential_usage(credential_name: str) -> str:
    """Check which workflows use a specific credential."""
    logger.info(f"Checking usage for credential: {credential_name}")
    client = get_client()
    
    try:
        wf_data = await client.get("/workflows")
        workflows = wf_data.get("data", [])
        
        using_workflows = []
        
        for wf in workflows:
            full_wf = await client.get(f"/workflows/{wf['id']}")
            wf_json = json.dumps(full_wf)
            
            if credential_name.lower() in wf_json.lower():
                using_workflows.append({
                    "id": wf["id"],
                    "name": wf["name"],
                    "active": wf.get("active", False)
                })
        
        return json.dumps({
            "status": "success",
            "credential_name": credential_name,
            "usage_count": len(using_workflows),
            "workflows": using_workflows
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)}, indent=2)
