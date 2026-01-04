"""
Semantic Intelligence Service - Business Logic Understanding
Provides workflow impact analysis, diagram generation, and semantic search.
"""
import json
import re
from typing import Dict, Any, Optional, List
from collections import defaultdict

from app.core.client import get_client, safe_tool
from app.core.logging import gateway_logger as logger


def _extract_node_data_fields(node: Dict[str, Any]) -> List[str]:
    """Extract data field references from node parameters."""
    fields = []
    params = node.get("parameters", {})
    
    # Convert to string and find all {{ expression }} patterns
    params_str = json.dumps(params)
    expressions = re.findall(r'\{\{([^}]+)\}\}', params_str)
    
    for expr in expressions:
        # Extract field references
        field_matches = re.findall(r'\$json\.(\w+)', expr)
        fields.extend(field_matches)
        
        # Also extract $input references
        input_matches = re.findall(r'\$input\.item\.json\.(\w+)', expr)
        fields.extend(input_matches)
    
    return list(set(fields))


@safe_tool
async def explain_workflow_impact(
    workflow_id: str,
    node_name: Optional[str] = None
) -> str:
    """
    Analyze and explain the business logic impact of a workflow or specific node.
    Identifies what data flows through, what external services are called,
    and what business outcomes are produced.
    
    Args:
        workflow_id: ID of the workflow to analyze.
        node_name: Optional specific node to focus on.
    
    Returns:
        JSON string with impact analysis.
    """
    logger.info(f"Analyzing workflow impact: {workflow_id}")
    
    client = get_client()
    
    try:
        workflow = await client.get(f"/workflows/{workflow_id}")
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        # Categorize nodes by type
        node_categories = {
            "triggers": [],
            "data_sources": [],
            "transformations": [],
            "actions": [],
            "integrations": []
        }
        
        integration_services = set()
        data_fields_used = set()
        
        for node in nodes:
            node_type = node.get("type", "")
            name = node.get("name", "")
            
            # Categorize by type pattern
            if "trigger" in node_type.lower() or "webhook" in node_type.lower():
                node_categories["triggers"].append(name)
            elif "http" in node_type.lower() or "api" in node_type.lower():
                node_categories["integrations"].append(name)
                # Extract service name from URL if possible
                params = node.get("parameters", {})
                url = params.get("url", "")
                if url:
                    import urllib.parse
                    try:
                        parsed = urllib.parse.urlparse(url)
                        if parsed.netloc:
                            integration_services.add(parsed.netloc)
                    except:
                        pass
            elif "set" in node_type.lower() or "code" in node_type.lower() or "function" in node_type.lower():
                node_categories["transformations"].append(name)
            elif "postgres" in node_type.lower() or "mysql" in node_type.lower() or "mongo" in node_type.lower():
                node_categories["data_sources"].append(name)
            else:
                node_categories["actions"].append(name)
            
            # Extract data fields
            fields = _extract_node_data_fields(node)
            data_fields_used.update(fields)
        
        # Analyze data flow
        data_flow = []
        for source_node, conns in connections.items():
            for output_type, targets in conns.items():
                for target in targets:
                    for connection in target:
                        data_flow.append({
                            "from": source_node,
                            "to": connection.get("node"),
                            "output_type": output_type
                        })
        
        # Build impact summary
        impact_summary = []
        
        if node_categories["triggers"]:
            impact_summary.append(f"Workflow starts from: {', '.join(node_categories['triggers'])}")
        
        if integration_services:
            impact_summary.append(f"External services called: {', '.join(integration_services)}")
        
        if node_categories["data_sources"]:
            impact_summary.append(f"Database operations: {', '.join(node_categories['data_sources'])}")
        
        if data_fields_used:
            impact_summary.append(f"Key data fields: {', '.join(list(data_fields_used)[:10])}")
        
        # Specific node analysis if requested
        node_detail = None
        if node_name:
            target_node = next((n for n in nodes if n.get("name") == node_name), None)
            if target_node:
                downstream = [f["to"] for f in data_flow if f["from"] == node_name]
                upstream = [f["from"] for f in data_flow if f["to"] == node_name]
                
                node_detail = {
                    "node_name": node_name,
                    "node_type": target_node.get("type"),
                    "receives_from": upstream,
                    "sends_to": downstream,
                    "data_fields_used": _extract_node_data_fields(target_node),
                    "impact": f"Changes to this node will affect: {', '.join(downstream) or 'workflow end'}"
                }
        
        return json.dumps({
            "status": "success",
            "workflow_id": workflow_id,
            "workflow_name": workflow.get("name"),
            "node_count": len(nodes),
            "node_categories": {k: v for k, v in node_categories.items() if v},
            "external_services": list(integration_services),
            "data_fields_referenced": list(data_fields_used)[:20],
            "data_flow_count": len(data_flow),
            "impact_summary": impact_summary,
            "specific_node_analysis": node_detail
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error analyzing workflow: {e}")
        return json.dumps({
            "status": "error",
            "workflow_id": workflow_id,
            "error": str(e)
        }, indent=2)


@safe_tool
async def generate_workflow_diagram(
    workflow_id: str,
    format: str = "mermaid"
) -> str:
    """
    Generate a visual diagram of the workflow.
    Outputs Mermaid syntax that can be rendered in markdown.
    
    Args:
        workflow_id: ID of the workflow to visualize.
        format: Output format (currently only 'mermaid' supported).
    
    Returns:
        JSON string with diagram code.
    """
    logger.info(f"Generating diagram for workflow: {workflow_id}")
    
    client = get_client()
    
    try:
        workflow = await client.get(f"/workflows/{workflow_id}")
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        # Build Mermaid flowchart
        mermaid_lines = ["graph TD"]
        
        # Define node styles based on type
        node_styles = {
            "trigger": "([{name}])",  # Stadium shape for triggers
            "action": "[{name}]",     # Rectangle for actions
            "function": "[/{name}/]", # Parallelogram for transforms
            "condition": "{{{name}}}", # Diamond for conditions
            "default": "[{name}]"
        }
        
        # Create node definitions
        for node in nodes:
            name = node.get("name", "Unknown")
            node_type = node.get("type", "").lower()
            safe_name = re.sub(r'[^\w\s]', '', name).replace(' ', '_')
            
            # Determine shape
            if "trigger" in node_type or "webhook" in node_type:
                shape = node_styles["trigger"]
            elif "if" in node_type or "switch" in node_type:
                shape = node_styles["condition"]
            elif "code" in node_type or "function" in node_type or "set" in node_type:
                shape = node_styles["function"]
            else:
                shape = node_styles["default"]
            
            display_name = name[:30] + "..." if len(name) > 30 else name
            mermaid_lines.append(f"    {safe_name}{shape.format(name=display_name)}")
        
        # Create connections
        for source_node, conns in connections.items():
            safe_source = re.sub(r'[^\w\s]', '', source_node).replace(' ', '_')
            
            for output_type, targets in conns.items():
                for target_list in targets:
                    for connection in target_list:
                        target_node = connection.get("node", "")
                        safe_target = re.sub(r'[^\w\s]', '', target_node).replace(' ', '_')
                        
                        label = ""
                        if output_type != "main":
                            label = f"|{output_type}|"
                        
                        mermaid_lines.append(f"    {safe_source} -->{label} {safe_target}")
        
        mermaid_code = "\n".join(mermaid_lines)
        
        return json.dumps({
            "status": "success",
            "workflow_id": workflow_id,
            "workflow_name": workflow.get("name"),
            "format": format,
            "node_count": len(nodes),
            "connection_count": sum(
                len(targets) 
                for conns in connections.values() 
                for target_list in conns.values()
                for targets in target_list
            ),
            "diagram": mermaid_code,
            "usage": "Copy the diagram code and paste in any Mermaid-compatible renderer"
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error generating diagram: {e}")
        return json.dumps({
            "status": "error",
            "workflow_id": workflow_id,
            "error": str(e)
        }, indent=2)


@safe_tool
async def semantic_search_workflows(query: str) -> str:
    """
    Search workflows using natural language.
    Searches in workflow names, node types, and node names.
    
    Args:
        query: Natural language search query.
    
    Returns:
        JSON string with matching workflows.
    """
    logger.info(f"Semantic search for: {query}")
    
    client = get_client()
    
    try:
        # Get all workflows
        wf_data = await client.get("/workflows")
        workflows = wf_data.get("data", [])
        
        # Normalize query
        query_terms = query.lower().split()
        
        results = []
        
        for wf in workflows:
            workflow_id = wf.get("id")
            workflow_name = wf.get("name", "").lower()
            
            # Get full workflow for node analysis
            full_wf = await client.get(f"/workflows/{workflow_id}")
            nodes = full_wf.get("nodes", [])
            
            # Collect searchable text
            searchable = [workflow_name]
            node_types = []
            node_names = []
            
            for node in nodes:
                node_name = node.get("name", "").lower()
                node_type = node.get("type", "").lower()
                node_names.append(node_name)
                node_types.append(node_type)
                searchable.append(node_name)
                searchable.append(node_type)
                
                # Include parameter values
                params = node.get("parameters", {})
                for key, value in params.items():
                    if isinstance(value, str):
                        searchable.append(value.lower())
            
            all_text = " ".join(searchable)
            
            # Score based on query matches
            score = 0
            matched_terms = []
            
            for term in query_terms:
                if term in all_text:
                    score += 1
                    matched_terms.append(term)
                    
                    # Bonus for name matches
                    if term in workflow_name:
                        score += 2
            
            if score > 0:
                results.append({
                    "workflow_id": workflow_id,
                    "workflow_name": wf.get("name"),
                    "active": wf.get("active"),
                    "relevance_score": score,
                    "matched_terms": matched_terms,
                    "node_count": len(nodes),
                    "node_types": list(set(node_types))[:5]
                })
        
        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return json.dumps({
            "status": "success",
            "query": query,
            "results_count": len(results),
            "results": results[:10]  # Top 10
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error in semantic search: {e}")
        return json.dumps({
            "status": "error",
            "query": query,
            "error": str(e)
        }, indent=2)


@safe_tool
async def map_data_flow(workflow_id: str) -> str:
    """
    Create a complete map of how data flows through a workflow.
    Tracks variable origins and destinations.
    
    Args:
        workflow_id: ID of the workflow to analyze.
    
    Returns:
        JSON string with data flow map.
    """
    logger.info(f"Mapping data flow for workflow: {workflow_id}")
    
    client = get_client()
    
    try:
        workflow = await client.get(f"/workflows/{workflow_id}")
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        # Build node index
        node_index = {n.get("name"): n for n in nodes}
        
        # Track data fields per node
        data_map = {}
        
        for node in nodes:
            name = node.get("name")
            node_type = node.get("type", "")
            params = node.get("parameters", {})
            
            # Extract input fields (what data this node uses)
            input_fields = _extract_node_data_fields(node)
            
            # Determine output fields (what data this node produces)
            output_fields = []
            
            # Set nodes explicitly define output
            if "set" in node_type.lower():
                values = params.get("values", {})
                for key in values.keys():
                    output_fields.append(key)
            # Code/Function nodes - analyze code for returns
            elif "code" in node_type.lower() or "function" in node_type.lower():
                code = params.get("jsCode", "") or params.get("functionCode", "")
                # Simple regex to find return object keys
                return_matches = re.findall(r'return\s*\{([^}]+)\}', code)
                for match in return_matches:
                    keys = re.findall(r'(\w+)\s*:', match)
                    output_fields.extend(keys)
            
            # Find upstream and downstream nodes
            upstream = []
            downstream = []
            
            for source, conns in connections.items():
                for output_type, targets in conns.items():
                    for target_list in targets:
                        for conn in target_list:
                            if conn.get("node") == name:
                                upstream.append(source)
                            if source == name:
                                downstream.append(conn.get("node"))
            
            data_map[name] = {
                "node_type": node_type,
                "input_fields_used": input_fields,
                "output_fields_produced": output_fields,
                "receives_from": list(set(upstream)),
                "sends_to": list(set(downstream))
            }
        
        return json.dumps({
            "status": "success",
            "workflow_id": workflow_id,
            "workflow_name": workflow.get("name"),
            "node_count": len(nodes),
            "data_map": data_map
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error mapping data flow: {e}")
        return json.dumps({
            "status": "error",
            "workflow_id": workflow_id,
            "error": str(e)
        }, indent=2)


@safe_tool
async def identify_bottlenecks(workflow_id: str) -> str:
    """
    Identify potential performance bottlenecks in a workflow.
    Analyzes node types, connections, and common patterns.
    
    Args:
        workflow_id: ID of the workflow to analyze.
    
    Returns:
        JSON string with bottleneck analysis.
    """
    logger.info(f"Identifying bottlenecks in workflow: {workflow_id}")
    
    client = get_client()
    
    try:
        workflow = await client.get(f"/workflows/{workflow_id}")
        nodes = workflow.get("nodes", [])
        connections = workflow.get("connections", {})
        
        bottlenecks = []
        recommendations = []
        
        # Analyze each node
        for node in nodes:
            name = node.get("name")
            node_type = node.get("type", "").lower()
            params = node.get("parameters", {})
            
            # Check for HTTP requests without timeout
            if "http" in node_type:
                if not params.get("timeout"):
                    bottlenecks.append({
                        "node": name,
                        "issue": "HTTP request without explicit timeout",
                        "severity": "medium"
                    })
                    recommendations.append(f"Add timeout to '{name}' HTTP node")
            
            # Check for code nodes with loops
            if "code" in node_type or "function" in node_type:
                code = params.get("jsCode", "") or params.get("functionCode", "")
                if "for" in code or "while" in code:
                    bottlenecks.append({
                        "node": name,
                        "issue": "Loop detected in code node",
                        "severity": "low"
                    })
            
            # Check for database queries without limits
            if "postgres" in node_type or "mysql" in node_type:
                query = params.get("query", "").lower()
                if "select" in query and "limit" not in query:
                    bottlenecks.append({
                        "node": name,
                        "issue": "SELECT query without LIMIT clause",
                        "severity": "high"
                    })
                    recommendations.append(f"Add LIMIT to query in '{name}'")
        
        # Check for fan-out (one node sending to many)
        for source, conns in connections.items():
            total_targets = sum(len(t) for targets in conns.values() for t in targets)
            if total_targets > 5:
                bottlenecks.append({
                    "node": source,
                    "issue": f"High fan-out: sends to {total_targets} nodes",
                    "severity": "medium"
                })
        
        # Check for long chains
        def count_chain_depth(node_name, visited=None):
            if visited is None:
                visited = set()
            if node_name in visited:
                return 0
            visited.add(node_name)
            
            max_depth = 0
            if node_name in connections:
                for output_type, targets in connections[node_name].items():
                    for target_list in targets:
                        for conn in target_list:
                            depth = count_chain_depth(conn.get("node"), visited.copy())
                            max_depth = max(max_depth, depth + 1)
            return max_depth
        
        for node in nodes:
            if "trigger" in node.get("type", "").lower():
                depth = count_chain_depth(node.get("name"))
                if depth > 10:
                    bottlenecks.append({
                        "node": node.get("name"),
                        "issue": f"Long execution chain: {depth} nodes deep",
                        "severity": "medium"
                    })
                    recommendations.append("Consider breaking into sub-workflows")
        
        return json.dumps({
            "status": "success",
            "workflow_id": workflow_id,
            "workflow_name": workflow.get("name"),
            "node_count": len(nodes),
            "bottlenecks_found": len(bottlenecks),
            "bottlenecks": bottlenecks,
            "recommendations": recommendations
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error identifying bottlenecks: {e}")
        return json.dumps({
            "status": "error",
            "workflow_id": workflow_id,
            "error": str(e)
        }, indent=2)
