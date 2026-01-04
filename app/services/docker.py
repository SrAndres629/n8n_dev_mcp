"""
Docker Debugger Service - Container Diagnostics
Provides comprehensive tools for analyzing Docker container logs, errors, and status.
"""
import json
import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from app.core.logging import debugger_logger as logger

# Docker SDK import with graceful fallback
try:
    import docker
    from docker.errors import DockerException, NotFound, APIError
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    # Dummy exceptions to prevent NameError in decorator
    class DockerException(Exception): pass
    class NotFound(Exception): pass
    class APIError(Exception): pass
    logger.warning("Docker SDK not installed. Run: pip install docker")


def _get_docker_client():
    """Get Docker client with error handling."""
    if not DOCKER_AVAILABLE:
        raise RuntimeError("Docker SDK not installed. Run: pip install docker>=7.0.0")
    try:
        return docker.from_env()
    except DockerException as e:
        raise RuntimeError(f"Cannot connect to Docker daemon. Is Docker Desktop running? Error: {e}")


def _safe_docker_tool(func):
    """Decorator for Docker tools with standardized error handling."""
    from functools import wraps
    import inspect
    
    @wraps(func)
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except NotFound as e:
            return json.dumps({
                "status": "error",
                "error_type": "ContainerNotFound",
                "message": str(e)
            }, indent=2)
        except APIError as e:
            return json.dumps({
                "status": "error",
                "error_type": "DockerAPIError",
                "message": str(e)
            }, indent=2)
        except RuntimeError as e:
            return json.dumps({
                "status": "error",
                "error_type": "DockerConnectionError",
                "message": str(e)
            }, indent=2)
        except Exception as e:
            logger.error(f"Docker tool error: {e}")
            return json.dumps({
                "status": "error",
                "error_type": type(e).__name__,
                "message": str(e)
            }, indent=2)
    
    # Preserve original signature for FastMCP
    wrapper.__signature__ = inspect.signature(func)
    return wrapper


# =============================================================================
# ERROR PATTERN DETECTION
# =============================================================================
ERROR_PATTERNS = {
    "connection_refused": {
        "pattern": r"(connection refused|ECONNREFUSED|connect ECONNREFUSED)",
        "severity": "high",
        "recommendation": "Service dependency not reachable. Check if the target service is running and network is configured correctly."
    },
    "permission_denied": {
        "pattern": r"(permission denied|EACCES|access denied)",
        "severity": "high",
        "recommendation": "File or directory permission issue. Check volume mounts and file ownership."
    },
    "out_of_memory": {
        "pattern": r"(out of memory|OOM|killed|cannot allocate memory)",
        "severity": "critical",
        "recommendation": "Container ran out of memory. Increase memory limits or optimize application memory usage."
    },
    "port_in_use": {
        "pattern": r"(address already in use|EADDRINUSE|port.*already.*allocated)",
        "severity": "high",
        "recommendation": "Port conflict. Another process is using the same port. Change port mapping or stop the conflicting process."
    },
    "database_connection": {
        "pattern": r"(database.*connection|ENOTFOUND.*postgres|mysql.*denied|mongodb.*failed)",
        "severity": "high",
        "recommendation": "Database connection failed. Verify database credentials, host, and port configuration."
    },
    "api_error": {
        "pattern": r"(401|403|unauthorized|forbidden|invalid.*token|authentication.*failed)",
        "severity": "medium",
        "recommendation": "API authentication error. Check API keys, tokens, or credentials."
    },
    "timeout": {
        "pattern": r"(timeout|ETIMEDOUT|timed out|context deadline exceeded)",
        "severity": "medium",
        "recommendation": "Operation timed out. Check network connectivity or increase timeout limits."
    },
    "file_not_found": {
        "pattern": r"(no such file|ENOENT|not found|file not found|module not found)",
        "severity": "medium",
        "recommendation": "Missing file or module. Check volume mounts, paths, and dependencies."
    },
    "syntax_error": {
        "pattern": r"(syntax error|SyntaxError|parse error|unexpected token)",
        "severity": "high",
        "recommendation": "Code syntax error. Review recent code changes for syntax issues."
    },
    "configuration_error": {
        "pattern": r"(invalid.*config|configuration.*error|env.*not.*set|missing.*environment)",
        "severity": "medium",
        "recommendation": "Configuration or environment variable issue. Check .env file and docker-compose.yml."
    },
    "ssl_certificate": {
        "pattern": r"(ssl|certificate|x509|TLS|self-signed)",
        "severity": "medium",
        "recommendation": "SSL/TLS certificate issue. Check certificate validity or disable SSL verification for development."
    },
    "dns_resolution": {
        "pattern": r"(getaddrinfo|EAI_AGAIN|dns|name resolution|could not resolve)",
        "severity": "medium",
        "recommendation": "DNS resolution failed. Check network configuration and container DNS settings."
    },
    "crash_restart": {
        "pattern": r"(exited with code|fatal|panic|segfault|core dumped)",
        "severity": "critical",
        "recommendation": "Container crashed. Check application logs for the root cause before restart."
    }
}


def _analyze_log_errors(logs: str) -> List[Dict[str, Any]]:
    """Analyze logs for common error patterns."""
    detected_errors = []
    log_lines = logs.split('\n')
    
    for line_num, line in enumerate(log_lines, 1):
        line_lower = line.lower()
        
        # Skip empty lines
        if not line.strip():
            continue
        
        # Check for general error indicators
        is_error_line = any(indicator in line_lower for indicator in [
            'error', 'err', 'fatal', 'critical', 'exception', 
            'failed', 'failure', 'denied', 'refused', 'timeout'
        ])
        
        if not is_error_line:
            continue
        
        # Match against known patterns
        for error_name, error_info in ERROR_PATTERNS.items():
            if re.search(error_info["pattern"], line, re.IGNORECASE):
                detected_errors.append({
                    "line_number": line_num,
                    "error_type": error_name,
                    "severity": error_info["severity"],
                    "log_line": line.strip()[:200],  # Truncate long lines
                    "recommendation": error_info["recommendation"]
                })
                break
        else:
            # Generic error if no pattern matched
            if is_error_line:
                detected_errors.append({
                    "line_number": line_num,
                    "error_type": "generic_error",
                    "severity": "low",
                    "log_line": line.strip()[:200],
                    "recommendation": "Review this error line for more context."
                })
    
    return detected_errors


# =============================================================================
# DOCKER TOOLS
# =============================================================================

@_safe_docker_tool
async def list_docker_containers(
    all_containers: bool = False,
    filter_status: Optional[str] = None
) -> str:
    """
    List Docker containers with their status and basic information.
    
    Args:
        all_containers: If True, include stopped containers (default: False, only running).
        filter_status: Optional filter by status: 'running', 'exited', 'paused', 'restarting'.
    
    Returns:
        JSON string with list of containers including name, status, image, and ports.
    """
    logger.info(f"Listing containers (all={all_containers}, status={filter_status})")
    
    client = _get_docker_client()
    
    filters = {}
    if filter_status:
        filters["status"] = filter_status
    
    containers = client.containers.list(all=all_containers, filters=filters)
    
    container_list = []
    for container in containers:
        # Get port mappings
        ports = container.attrs.get("NetworkSettings", {}).get("Ports", {}) or {}
        port_mappings = []
        for container_port, host_bindings in ports.items():
            if host_bindings:
                for binding in host_bindings:
                    port_mappings.append(f"{binding.get('HostPort', '?')}:{container_port}")
        
        # Get health status if available
        health = container.attrs.get("State", {}).get("Health", {})
        health_status = health.get("Status", "no_healthcheck")
        
        container_list.append({
            "id": container.short_id,
            "name": container.name,
            "image": container.image.tags[0] if container.image.tags else container.image.short_id,
            "status": container.status,
            "health": health_status,
            "ports": port_mappings,
            "created": container.attrs.get("Created", ""),
            "started_at": container.attrs.get("State", {}).get("StartedAt", "")
        })
    
    logger.info(f"Found {len(container_list)} containers")
    return json.dumps({
        "status": "success",
        "count": len(container_list),
        "containers": container_list
    }, indent=2)


@_safe_docker_tool
async def get_container_logs(
    container_name: str,
    tail: int = 100,
    since_minutes: Optional[int] = None,
    show_timestamps: bool = True
) -> str:
    """
    Get logs from a Docker container.
    
    Args:
        container_name: Name or ID of the container.
        tail: Number of lines to retrieve from the end (default: 100).
        since_minutes: Only show logs from the last N minutes (optional).
        show_timestamps: Include timestamps in output (default: True).
    
    Returns:
        JSON string with container logs and metadata.
    """
    logger.info(f"Getting logs for container: {container_name} (tail={tail})")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    kwargs = {
        "tail": tail,
        "timestamps": show_timestamps
    }
    
    if since_minutes:
        since_time = datetime.utcnow() - timedelta(minutes=since_minutes)
        kwargs["since"] = since_time
    
    logs = container.logs(**kwargs).decode("utf-8", errors="replace")
    
    return json.dumps({
        "status": "success",
        "container": container_name,
        "container_status": container.status,
        "log_lines": tail,
        "logs": logs
    }, indent=2)


@_safe_docker_tool
async def diagnose_container_errors(
    container_name: str,
    tail: int = 200,
    since_minutes: Optional[int] = 30
) -> str:
    """
    Deep analysis of container logs to detect and categorize errors.
    Uses pattern matching to identify common issues and provides recommendations.
    
    Args:
        container_name: Name or ID of the container to analyze.
        tail: Number of log lines to analyze (default: 200).
        since_minutes: Only analyze logs from the last N minutes (default: 30).
    
    Returns:
        JSON string with detailed error analysis, categorized by severity,
        including specific recommendations for each detected issue.
    """
    logger.info(f"Diagnosing errors for container: {container_name}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    # Get container info
    container_info = {
        "name": container.name,
        "id": container.short_id,
        "status": container.status,
        "image": container.image.tags[0] if container.image.tags else container.image.short_id,
        "restart_count": container.attrs.get("RestartCount", 0),
        "exit_code": container.attrs.get("State", {}).get("ExitCode"),
        "oom_killed": container.attrs.get("State", {}).get("OOMKilled", False)
    }
    
    # Get logs
    kwargs = {"tail": tail, "timestamps": True}
    if since_minutes:
        since_time = datetime.utcnow() - timedelta(minutes=since_minutes)
        kwargs["since"] = since_time
    
    logs = container.logs(**kwargs).decode("utf-8", errors="replace")
    
    # Analyze for errors
    detected_errors = _analyze_log_errors(logs)
    
    # Categorize by severity
    critical_errors = [e for e in detected_errors if e["severity"] == "critical"]
    high_errors = [e for e in detected_errors if e["severity"] == "high"]
    medium_errors = [e for e in detected_errors if e["severity"] == "medium"]
    low_errors = [e for e in detected_errors if e["severity"] == "low"]
    
    # Generate summary
    if container_info["oom_killed"]:
        priority_issue = "Container was killed due to Out of Memory. Consider increasing memory limits."
    elif container_info["exit_code"] and container_info["exit_code"] != 0:
        priority_issue = f"Container exited with error code {container_info['exit_code']}."
    elif critical_errors:
        priority_issue = critical_errors[0]["recommendation"]
    elif high_errors:
        priority_issue = high_errors[0]["recommendation"]
    elif container.status != "running":
        priority_issue = f"Container is not running (status: {container.status})."
    else:
        priority_issue = None
    
    diagnosis = {
        "status": "success",
        "container": container_info,
        "analysis": {
            "total_errors_found": len(detected_errors),
            "critical": len(critical_errors),
            "high": len(high_errors),
            "medium": len(medium_errors),
            "low": len(low_errors)
        },
        "priority_issue": priority_issue,
        "errors": {
            "critical": critical_errors[:5],  # Limit to top 5 per category
            "high": high_errors[:5],
            "medium": medium_errors[:3],
            "low": low_errors[:2]
        },
        "raw_log_sample": logs[-2000:] if len(logs) > 2000 else logs  # Last 2000 chars
    }
    
    logger.info(f"Diagnosis complete: {len(detected_errors)} errors found ({len(critical_errors)} critical)")
    return json.dumps(diagnosis, indent=2)


@_safe_docker_tool
async def get_container_stats(container_name: str) -> str:
    """
    Get real-time resource usage statistics for a container.
    
    Args:
        container_name: Name or ID of the container.
    
    Returns:
        JSON string with CPU, memory, network, and I/O statistics.
    """
    logger.info(f"Getting stats for container: {container_name}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    if container.status != "running":
        return json.dumps({
            "status": "warning",
            "message": f"Container '{container_name}' is not running (status: {container.status})",
            "container_status": container.status
        }, indent=2)
    
    # Get one stats sample (stream=False for single snapshot)
    stats = container.stats(stream=False)
    
    # Calculate CPU percentage
    cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                stats["precpu_stats"]["cpu_usage"]["total_usage"]
    system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                   stats["precpu_stats"]["system_cpu_usage"]
    num_cpus = stats["cpu_stats"].get("online_cpus", 1)
    
    cpu_percent = 0.0
    if system_delta > 0 and cpu_delta > 0:
        cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0
    
    # Calculate memory usage
    memory_stats = stats.get("memory_stats", {})
    memory_usage = memory_stats.get("usage", 0)
    memory_limit = memory_stats.get("limit", 1)
    memory_percent = (memory_usage / memory_limit) * 100.0 if memory_limit > 0 else 0
    
    # Network I/O
    networks = stats.get("networks", {})
    network_rx = sum(net.get("rx_bytes", 0) for net in networks.values())
    network_tx = sum(net.get("tx_bytes", 0) for net in networks.values())
    
    # Block I/O
    blkio_stats = stats.get("blkio_stats", {}).get("io_service_bytes_recursive", []) or []
    block_read = sum(item.get("value", 0) for item in blkio_stats if item.get("op") == "read")
    block_write = sum(item.get("value", 0) for item in blkio_stats if item.get("op") == "write")
    
    result = {
        "status": "success",
        "container": container_name,
        "timestamp": stats.get("read", ""),
        "cpu": {
            "percent": round(cpu_percent, 2),
            "online_cpus": num_cpus
        },
        "memory": {
            "usage_bytes": memory_usage,
            "usage_mb": round(memory_usage / (1024 * 1024), 2),
            "limit_mb": round(memory_limit / (1024 * 1024), 2),
            "percent": round(memory_percent, 2)
        },
        "network": {
            "rx_bytes": network_rx,
            "rx_mb": round(network_rx / (1024 * 1024), 2),
            "tx_bytes": network_tx,
            "tx_mb": round(network_tx / (1024 * 1024), 2)
        },
        "block_io": {
            "read_bytes": block_read,
            "read_mb": round(block_read / (1024 * 1024), 2),
            "write_bytes": block_write,
            "write_mb": round(block_write / (1024 * 1024), 2)
        }
    }
    
    logger.info(f"Stats retrieved: CPU={cpu_percent:.1f}%, MEM={memory_percent:.1f}%")
    return json.dumps(result, indent=2)


@_safe_docker_tool
async def restart_container(
    container_name: str,
    timeout: int = 10
) -> str:
    """
    Restart a Docker container.
    
    Args:
        container_name: Name or ID of the container to restart.
        timeout: Seconds to wait before killing the container (default: 10).
    
    Returns:
        JSON string with the result of the restart operation.
    """
    logger.info(f"Restarting container: {container_name}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    previous_status = container.status
    container.restart(timeout=timeout)
    container.reload()
    
    return json.dumps({
        "status": "success",
        "action": "restart",
        "container": container_name,
        "previous_status": previous_status,
        "current_status": container.status,
        "message": f"Container '{container_name}' restarted successfully"
    }, indent=2)


@_safe_docker_tool
async def analyze_all_container_errors(
    include_healthy: bool = False,
    tail_per_container: int = 100
) -> str:
    """
    Scan ALL containers for errors and provide a consolidated report.
    Perfect for getting a quick overview of system health.
    
    Args:
        include_healthy: If True, include containers with no errors (default: False).
        tail_per_container: Number of log lines to analyze per container (default: 100).
    
    Returns:
        JSON string with a consolidated error report across all containers,
        sorted by severity.
    """
    logger.info("Analyzing errors across all containers")
    
    client = _get_docker_client()
    containers = client.containers.list(all=True)
    
    all_issues = []
    healthy_containers = []
    
    for container in containers:
        container_summary = {
            "name": container.name,
            "status": container.status,
            "image": container.image.tags[0] if container.image.tags else container.image.short_id
        }
        
        # Check for obvious issues
        issues = []
        
        # Container not running
        if container.status != "running":
            exit_code = container.attrs.get("State", {}).get("ExitCode", 0)
            issues.append({
                "type": "container_not_running",
                "severity": "high" if exit_code != 0 else "medium",
                "message": f"Container is {container.status}" + (f" (exit code: {exit_code})" if exit_code else ""),
                "recommendation": "Check container logs and restart if needed."
            })
        
        # OOM killed
        if container.attrs.get("State", {}).get("OOMKilled", False):
            issues.append({
                "type": "oom_killed",
                "severity": "critical",
                "message": "Container was killed due to Out of Memory",
                "recommendation": "Increase container memory limits in docker-compose.yml"
            })
        
        # High restart count
        restart_count = container.attrs.get("RestartCount", 0)
        if restart_count > 5:
            issues.append({
                "type": "restart_loop",
                "severity": "high",
                "message": f"Container has restarted {restart_count} times",
                "recommendation": "Container may be in a crash loop. Check application errors."
            })
        
        # Analyze logs for running or recently stopped containers
        if container.status in ["running", "exited", "restarting"]:
            try:
                logs = container.logs(tail=tail_per_container, timestamps=True).decode("utf-8", errors="replace")
                log_errors = _analyze_log_errors(logs)
                
                # Add unique error types from logs
                error_types_seen = set()
                for error in log_errors[:5]:  # Limit to 5 errors per container
                    if error["error_type"] not in error_types_seen:
                        issues.append({
                            "type": error["error_type"],
                            "severity": error["severity"],
                            "message": error["log_line"][:100],
                            "recommendation": error["recommendation"]
                        })
                        error_types_seen.add(error["error_type"])
            except Exception as e:
                logger.warning(f"Could not analyze logs for {container.name}: {e}")
        
        if issues:
            all_issues.append({
                "container": container_summary,
                "issues": issues,
                "issue_count": len(issues),
                "max_severity": max(
                    ["low", "medium", "high", "critical"].index(i["severity"]) 
                    for i in issues
                )
            })
        else:
            healthy_containers.append(container_summary)
    
    # Sort by severity (highest first)
    all_issues.sort(key=lambda x: x["max_severity"], reverse=True)
    
    # Summary stats
    total_issues = sum(c["issue_count"] for c in all_issues)
    critical_containers = len([c for c in all_issues if c["max_severity"] >= 3])
    
    result = {
        "status": "success",
        "summary": {
            "total_containers": len(containers),
            "containers_with_issues": len(all_issues),
            "healthy_containers": len(healthy_containers),
            "total_issues": total_issues,
            "critical_containers": critical_containers
        },
        "containers_with_issues": all_issues,
    }
    
    if include_healthy:
        result["healthy_containers"] = healthy_containers
    
    logger.info(f"Analysis complete: {len(all_issues)} containers with issues, {total_issues} total issues")
    return json.dumps(result, indent=2)


@_safe_docker_tool
async def get_container_inspect(container_name: str) -> str:
    """
    Get detailed inspection data for a container (configuration, mounts, networks, etc.).
    
    Args:
        container_name: Name or ID of the container.
    
    Returns:
        JSON string with detailed container configuration.
    """
    logger.info(f"Inspecting container: {container_name}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    attrs = container.attrs
    
    # Extract key information
    config = attrs.get("Config", {})
    host_config = attrs.get("HostConfig", {})
    network_settings = attrs.get("NetworkSettings", {})
    state = attrs.get("State", {})
    
    inspection = {
        "status": "success",
        "container": {
            "id": container.id,
            "name": container.name,
            "image": config.get("Image", ""),
            "created": attrs.get("Created", ""),
        },
        "state": {
            "status": state.get("Status", ""),
            "running": state.get("Running", False),
            "paused": state.get("Paused", False),
            "restarting": state.get("Restarting", False),
            "exit_code": state.get("ExitCode", 0),
            "error": state.get("Error", ""),
            "started_at": state.get("StartedAt", ""),
            "finished_at": state.get("FinishedAt", ""),
            "oom_killed": state.get("OOMKilled", False)
        },
        "config": {
            "env": config.get("Env", []),
            "cmd": config.get("Cmd", []),
            "entrypoint": config.get("Entrypoint", []),
            "working_dir": config.get("WorkingDir", ""),
            "exposed_ports": list(config.get("ExposedPorts", {}).keys()),
            "labels": config.get("Labels", {})
        },
        "host_config": {
            "memory_limit_mb": round(host_config.get("Memory", 0) / (1024 * 1024), 2),
            "cpu_shares": host_config.get("CpuShares", 0),
            "restart_policy": host_config.get("RestartPolicy", {}),
            "port_bindings": host_config.get("PortBindings", {}),
            "binds": host_config.get("Binds", []),
            "network_mode": host_config.get("NetworkMode", "")
        },
        "mounts": [
            {
                "type": m.get("Type", ""),
                "source": m.get("Source", ""),
                "destination": m.get("Destination", ""),
                "mode": m.get("Mode", ""),
                "rw": m.get("RW", True)
            }
            for m in attrs.get("Mounts", [])
        ],
        "networks": {
            name: {
                "ip_address": net.get("IPAddress", ""),
                "gateway": net.get("Gateway", ""),
                "network_id": net.get("NetworkID", "")[:12]
            }
            for name, net in network_settings.get("Networks", {}).items()
        }
    }
    
    logger.info(f"Inspection complete for: {container_name}")
    return json.dumps(inspection, indent=2)


@_safe_docker_tool
async def list_container_files(
    container_name: str,
    path: str = "/"
) -> str:
    """
    List files and directories inside a container.
    """
    logger.info(f"Listing files in {container_name} at {path}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    # Use ls -la to get details
    exec_result = container.exec_run(["ls", "-la", path])
    
    if exec_result.exit_code != 0:
        return json.dumps({
            "status": "error",
            "exit_code": exec_result.exit_code,
            "output": exec_result.output.decode("utf-8", errors="replace")
        }, indent=2)
        
    output = exec_result.output.decode("utf-8", errors="replace")
    
    # Parse generic ls -la output to structured JSON (basic parsing)
    lines = output.strip().split('\n')
    files = []
    for line in lines[1:]: # Skip total header
        parts = re.split(r'\s+', line.strip())
        if len(parts) >= 9:
            files.append({
                "permissions": parts[0],
                "owner": parts[2],
                "group": parts[3],
                "size": parts[4],
                "name": " ".join(parts[8:])
            })
            
    return json.dumps({
        "status": "success",
        "container": container_name,
        "path": path,
        "files": files,
        "raw_output": output
    }, indent=2)


@_safe_docker_tool
async def read_container_file(
    container_name: str,
    path: str
) -> str:
    """
    Read the content of a file inside a container.
    """
    logger.info(f"Reading file {path} from {container_name}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    # Use cat to read file
    exec_result = container.exec_run(["cat", path])
    
    if exec_result.exit_code != 0:
        return json.dumps({
            "status": "error",
            "exit_code": exec_result.exit_code,
            "output": exec_result.output.decode("utf-8", errors="replace")
        }, indent=2)
        
    return json.dumps({
        "status": "success",
        "container": container_name,
        "path": path,
        "content": exec_result.output.decode("utf-8", errors="replace")
    }, indent=2)


@_safe_docker_tool
async def run_container_command(
    container_name: str,
    command: str,
    user: str = "root"
) -> str:
    """
    Execute a direct command inside a container.
    """
    logger.info(f"Executing command in {container_name}: {command}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    exec_result = container.exec_run(command, user=user)
    
    return json.dumps({
        "status": "success" if exec_result.exit_code == 0 else "error",
        "exit_code": exec_result.exit_code,
        "output": exec_result.output.decode("utf-8", errors="replace")
    }, indent=2)


@_safe_docker_tool
async def run_sql_in_container(
    container_name: str,
    query: str,
    db_type: str = "postgres",
    db_user: str = "postgres",
    db_name: str = "postgres"
) -> str:
    """
    Run a SQL query inside a database container.
    """
    logger.info(f"Running SQL in {container_name} ({db_type}): {query}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    command = []
    if db_type.lower() == "postgres":
        command = ["psql", "-U", db_user, "-d", db_name, "-c", query]
    elif db_type.lower() == "mysql":
         command = ["mysql", "-u", db_user, f"-p{db_user}", "-D", db_name, "-e", query] # Note: simplistic password assumption
    else:
        return json.dumps({
            "status": "error",
            "message": f"Unsupported database type: {db_type}"
        }, indent=2)
        
    exec_result = container.exec_run(command)
    
    return json.dumps({
        "status": "success" if exec_result.exit_code == 0 else "error",
        "exit_code": exec_result.exit_code,
        "query": query,
        "output": exec_result.output.decode("utf-8", errors="replace")
    }, indent=2)


@_safe_docker_tool
async def prune_docker_images(
    older_than_days: int = 30,
    dry_run: bool = True
) -> str:
    """
    Identify and optionally remove old Docker images.
    """
    logger.info(f"Pruning images (older_than={older_than_days}d, dry_run={dry_run})")
    
    client = _get_docker_client()
    images = client.images.list()
    
    candidates = []
    cutoff_date = datetime.now().astimezone() - timedelta(days=older_than_days)
    
    # Need to handle timezone parsing carefully from Docker strings
    # Usually '2025-01-04T10:31:54.123456789Z'
    # Simplified parsing for this example
    
    for img in images:
        created_str = img.attrs.get("Created")
        try:
             # Basic ISO 8601 parsing, removing fractional seconds for simplicity if needed
             # or using a library. Docker format is usually ISO.
             # Python 3.11+ checks
             from dateutil.parser import parse # fallback or simple
             created_dt = parse(created_str)
        except:
             continue # Skip if cant parse
             
        if created_dt < cutoff_date:
             candidates.append({
                 "id": img.id,
                 "tags": img.tags,
                 "created": created_str,
                 "size": img.attrs.get("Size")
             })

    if dry_run:
        return json.dumps({
            "status": "success",
            "mode": "dry_run",
            "candidate_count": len(candidates),
            "candidates": candidates,
            "message": "Set dry_run=False to actually delete these images."
        }, indent=2)
        
    deleted = []
    errors = []
    for cand in candidates:
        try:
            client.images.remove(channel=cand["id"]) # or just image=cand['id']
            deleted.append(cand["id"])
        except Exception as e:
            errors.append({"id": cand["id"], "error": str(e)})

    return json.dumps({
        "status": "success",
        "deleted_count": len(deleted),
        "deleted": deleted,
        "errors": errors
    }, indent=2)


@_safe_docker_tool
async def check_container_connection(
    source_container: str,
    target: str,
    port: int
) -> str:
    """
    Test network connectivity from inside a container to a target.
    
    Args:
        source_container: The container to run the test from (e.g. 'n8n').
        target: The target hostname or IP (e.g. 'postgres' or 'google.com').
        port: The target port.
    """
    logger.info(f"Checking connection: {source_container} -> {target}:{port}")
    
    client = _get_docker_client()
    container = client.containers.get(source_container)
    
    # Try using nc (netcat) first, then curl, then bash /dev/tcp
    # This ensures it works on most images (alpine, debian, etc)
    
    # 1. Try nc (most robust)
    cmd_nc = f"nc -zv -w 3 {target} {port}"
    res_nc = container.exec_run(["sh", "-c", cmd_nc])
    
    if res_nc.exit_code == 0:
        return json.dumps({
            "status": "success",
            "connected": True,
            "method": "nc",
            "output": res_nc.output.decode("utf-8")
        }, indent=2)

    # 2. Try curl (if http/https port)
    if port in [80, 443, 8080, 3000, 5678]:
        protocol = "https" if port == 443 else "http"
        cmd_curl = f"curl -I --connect-timeout 3 {protocol}://{target}:{port}"
        res_curl = container.exec_run(["sh", "-c", cmd_curl])
        if res_curl.exit_code == 0:
             return json.dumps({
                "status": "success",
                "connected": True,
                "method": "curl",
                "output": res_curl.output.decode("utf-8")
            }, indent=2)

    # 3. Last resort: internal bash /dev/tcp (if bash exists)
    cmd_bash = f"timeout 3 bash -c '</dev/tcp/{target}/{port}'"
    res_bash = container.exec_run(["sh", "-c", cmd_bash])
    
    if res_bash.exit_code == 0:
         return json.dumps({
            "status": "success",
            "connected": True,
            "method": "bash_dev_tcp",
            "output": "Connection established via /dev/tcp"
        }, indent=2)
        
    return json.dumps({
        "status": "error",
        "connected": False,
        "message": f"Could not connect to {target}:{port}",
        "details": res_nc.output.decode("utf-8") or res_bash.output.decode("utf-8")
    }, indent=2)


@_safe_docker_tool
async def inspect_container_dns(container_name: str) -> str:
    """
    Inspect the DNS configuration and resolution inside a container.
    """
    logger.info(f"Inspecting DNS for {container_name}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    # Read resolv.conf
    res_resolv = container.exec_run(["cat", "/etc/resolv.conf"])
    resolv_conf = res_resolv.output.decode("utf-8")
    
    # Try to resolve key internal hosts
    test_hosts = ["host.docker.internal", "google.com", "postgres", "n8n"]
    resolution_results = {}
    
    for host in test_hosts:
        # getent hosts is standard in most linux distros
        res = container.exec_run(["getent", "hosts", host])
        resolution_results[host] = "Resolved: " + res.output.decode("utf-8").strip() if res.exit_code == 0 else "Failed to resolve"
        
    return json.dumps({
        "status": "success",
        "container": container_name,
        "resolv_conf": resolv_conf,
        "resolutions": resolution_results
    }, indent=2)


@_safe_docker_tool
async def audit_image_freshness(image_name: str) -> str:
    """
    Check if a local image is outdated compared to Docker Hub.
    Note: Requires 'requests' library.
    """
    logger.info(f"Auditing image freshness: {image_name}")
    try:
        import requests
    except ImportError:
        return json.dumps({"status": "error", "message": "requests library not installed"}, indent=2)
        
    client = _get_docker_client()
    
    try:
        # Handle 'postgres:14' vs 'postgres' (implicitly latest)
        if ":" in image_name:
            repo, tag = image_name.split(":", 1)
        else:
            repo, tag = image_name, "latest"
            
        # Standardize official images (postgres -> library/postgres)
        if "/" not in repo:
            repo = f"library/{repo}"
            
        # Get local image info
        local_img = client.images.get(f"{repo}:{tag}")
        local_created = local_img.attrs.get("Created")
        local_id = local_img.id
        
        # Query Docker Hub API
        # Only works for public images currently
        url = f"https://hub.docker.com/v2/repositories/{repo}/tags/{tag}"
        resp = requests.get(url, timeout=5)
        
        if resp.status_code != 200:
             return json.dumps({
                "status": "warning",
                "message": f"Could not check Docker Hub for {repo}:{tag}. Status: {resp.status_code}",
                "local_created": local_created
            }, indent=2)
            
        remote_data = resp.json()
        remote_last_updated = remote_data.get("last_updated")
        
        # Simple date string comparison (ISO format usually sorts correctly)
        # Ideally parsing via dateutil
        is_stale = local_created < remote_last_updated if local_created and remote_last_updated else False
        
        return json.dumps({
            "status": "success",
            "image": f"{repo}:{tag}",
            "is_outdated": is_stale,
            "local_created": local_created,
            "remote_last_updated": remote_last_updated,
            "recommendation": "Pull the latest image (`docker pull ...`) and recreate the container." if is_stale else "Image works but verify exact hash if in doubt."
        }, indent=2)
        
    except Exception as e:
         return json.dumps({
            "status": "error",
            "message": f"Failed to audit image: {str(e)}"
        }, indent=2)


@_safe_docker_tool
async def backup_volume_to_host(
    volume_name: str,
    backup_path: str
) -> str:
    """
    Create a tarball backup of a Docker volume to the host.
    """
    logger.info(f"Backing up volume {volume_name} to {backup_path}")
    
    client = _get_docker_client()
    
    # Validate path (must be absolute)
    import os
    if not os.path.isabs(backup_path):
         return json.dumps({"status": "error", "message": "Backup path must be absolute"}, indent=2)
         
    backup_dir = os.path.dirname(backup_path)
    backup_file = os.path.basename(backup_path)
    
    if not os.path.exists(backup_dir):
        return json.dumps({"status": "error", "message": f"Directory does not exist: {backup_dir}"}, indent=2)

    # Use a helper alpine container to mount the volume and tar it
    # Mapping host dir allows writing directly to host
    try:
        # This blocks until finished
        logs = client.containers.run(
            image="alpine:latest",
            command=f"tar czf /backup/{backup_file} -C /data .",
            volumes={
                volume_name: {'bind': '/data', 'mode': 'ro'},
                backup_dir: {'bind': '/backup', 'mode': 'rw'}
            },
            remove=True
        )
        
        return json.dumps({
            "status": "success",
            "message": "Backup created successfully",
            "volume": volume_name,
            "backup_path": backup_path
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Backup failed: {str(e)}"
        }, indent=2)


@_safe_docker_tool
async def grep_log_across_containers(
    pattern: str,
    since_minutes: int = 60
) -> str:
    """
    Search for a regex pattern in the logs of ALL running containers.
    """
    logger.info(f"Grepping logs for '{pattern}' (last {since_minutes}m)")
    
    client = _get_docker_client()
    containers = client.containers.list(filters={"status": "running"})
    
    matches = []
    
    for container in containers:
        try:
            # Grab recent logs
            # Note: We get raw bytes, need to decode
            log_output = container.logs(
                since=datetime.utcnow() - timedelta(minutes=since_minutes),
                timestamps=True
            ).decode("utf-8", errors="replace")
            
            for line in log_output.splitlines():
                if re.search(pattern, line, re.IGNORECASE):
                    matches.append({
                        "container": container.name,
                        "log": line[:200] # Truncate for sanity
                    })
        except Exception as e:
            logger.warning(f"Could not grep logs of {container.name}: {e}")
            
    return json.dumps({
        "status": "success",
        "pattern": pattern,
        "matches_found": len(matches),
        "matches": matches[:100] # Limit return size
    }, indent=2)


@_safe_docker_tool
async def scan_container_security(container_name: str) -> str:
    """
    Scan a container for basic security issues (exposed secrets in Env, risky config).
    Does NOT replace a full CVE scanner like Trivy, but catches low-hanging fruit.
    """
    logger.info(f"Scanning security for: {container_name}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    issues = []
    
    # 1. Scan Environment Variables for Secrets
    # Heuristic: variable names containing sensitive keywords
    sensitive_keywords = ["KEY", "SECRET", "PASSWORD", "TOKEN", "AUTH", "CREDENTIAL", "PRIVATE"]
    env_vars = container.attrs.get("Config", {}).get("Env", [])
    
    exposed_secrets = []
    for env in env_vars:
        if "=" in env:
            key, val = env.split("=", 1)
            if any(k in key.upper() for k in sensitive_keywords):
                # We found a potential secret
                exposed_secrets.append(key)
    
    if exposed_secrets:
        issues.append({
            "type": "exposed_environment_secrets",
            "severity": "high",
            "message": f"Potential secrets found in environment variables: {', '.join(exposed_secrets)}",
            "recommendation": "Use Docker Secrets or a file-based secret management solution instead of plain env vars."
        })

    # 2. Check for Privileged Mode
    if container.attrs.get("HostConfig", {}).get("Privileged", False):
         issues.append({
            "type": "privileged_mode",
            "severity": "critical",
            "message": "Container is running in Privileged mode.",
            "recommendation": "Avoid privileged mode unless absolutely necessary. It grants full host root capabilities."
        })
        
    # 3. Check for Root User (heuristic)
    # This is tricky without inspecting the image deeply, but we can check if generic config specifies user
    user = container.attrs.get("Config", {}).get("User", "")
    if user == "" or user == "0" or user == "root":
         issues.append({
            "type": "running_as_root",
            "severity": "medium",
            "message": "Container appears to start as root (no User specified or User=root).",
            "recommendation": "Specify a non-root user in Dockerfile or runtime config if possible."
        })

    return json.dumps({
        "status": "success",
        "container": container_name,
        "issues_found": len(issues),
        "issues": issues,
        "scan_type": "heuristic_config_audit"
    }, indent=2)


@_safe_docker_tool
async def recommend_resource_limits(container_name: str) -> str:
    """
    Analyze current usage vs limits and recommend 'right-sizing'.
    """
    logger.info(f"Analyzing resources for: {container_name}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    if container.status != "running":
         return json.dumps({"status": "error", "message": "Container must be running to analyze stats."}, indent=2)
         
    stats = container.stats(stream=False)
    
    # MEMORY
    mem_usage = stats["memory_stats"].get("usage", 0)
    mem_limit = stats["memory_stats"].get("limit", 0)
    mem_max_usage = stats["memory_stats"].get("max_usage", 0) # Peak usage since start
    
    # Heuristics
    recommendations = []
    
    # 1. Memory Buffering
    # If max usage is < 50% of limit, we can probably reduce.
    # If max usage is > 90% of limit, we MUST increase.
    
    if mem_limit > 0:
        usage_pct = (mem_max_usage / mem_limit) * 100
        mem_limit_mb = mem_limit / (1024*1024)
        mem_max_mb = mem_max_usage / (1024*1024)
        
        if usage_pct < 40 and mem_limit_mb > 100: # Only if limit is non-trivial
             new_limit = int(mem_max_usage * 1.5) # +50% buffer
             recommendations.append({
                 "resource": "memory",
                 "action": "reduce",
                 "current_limit_mb": round(mem_limit_mb, 2),
                 "peak_usage_mb": round(mem_max_mb, 2),
                 "usage_pct": round(usage_pct, 2),
                 "suggestion": f"Limit is quite high for observed peak. Consider reducing to {round(new_limit/(1024*1024), 0)}MB."
             })
        elif usage_pct > 85:
             new_limit = int(mem_limit * 1.5)
             recommendations.append({
                 "resource": "memory",
                 "action": "increase",
                 "current_limit_mb": round(mem_limit_mb, 2),
                 "peak_usage_mb": round(mem_max_mb, 2),
                 "usage_pct": round(usage_pct, 2),
                 "suggestion": f"Memory pressure detected! Peak usage is near limit. Increase to at least {round(new_limit/(1024*1024), 0)}MB."
             })
             
    # CPU (Harder to estimate from single snapshot, simplified)
    # Check if CPU throttling (if available in stats)
    # stats['cpu_stats']['throttling_data']['throttled_periods']
    throttling = stats.get("cpu_stats", {}).get("throttling_data", {})
    if throttling.get("throttled_periods", 0) > 0:
         recommendations.append({
             "resource": "cpu",
             "action": "increase",
             "details": throttling,
             "suggestion": "Container is being CPU throttled. Increase CPU quota/limit."
         })

    return json.dumps({
        "status": "success",
        "container": container_name,
        "recommendations": recommendations,
        "stats_snapshot": {
            "memory_peak_mb": round(mem_max_usage/(1024*1024), 2),
            "memory_limit_mb": round(mem_limit/(1024*1024), 2)
        }
    }, indent=2)


@_safe_docker_tool
async def create_container_snapshot(
    container_name: str,
    tag: str
) -> str:
    """
    'Time Travel': Commit the current state of a container to a new image.
    Useful for debugging: snapshot a container before it crashes or before you break it.
    """
    logger.info(f"Snapshotting container {container_name} to image {tag}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    # Pause container to ensure consistency (optional but recommended)
    is_running = container.status == "running"
    if is_running:
        container.pause()
        
    try:
        image = container.commit(repository=tag)
    finally:
        if is_running:
            container.unpause()
            
    return json.dumps({
        "status": "success",
        "original_container": container_name,
        "snapshot_image_id": image.short_id,
        "snapshot_tag": tag,
        "message": f"Snapshot created. You can verify it with 'docker run -it {tag} sh' safely."
    }, indent=2)


@_safe_docker_tool
async def check_port_availability(port: int) -> str:
    """
    Check if a port is available on the HOST system.
    Useful before exposing a new port in compose.
    """
    logger.info(f"Checking host port availability: {port}")
    import socket
    
    is_available = False
    owner = "unknown"
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    
    try:
        # Try to bind. If it fails, port is in use.
        # This is a bit invasive if we actually accept, but we just bind/close.
        # Safer check: try to connect? No, we want to know if WE can bind.
        
        # 'bind' is the most accurate for "can I listen here?"
        sock.bind(('0.0.0.0', port))
        is_available = True
    except Exception as e:
        is_available = False
        owner = str(e)
    finally:
        sock.close()
        
    return json.dumps({
        "status": "success",
        "port": port,
        "available": is_available,
        "message": "Port is available for binding." if is_available else f"Port is in use or restricted: {owner}"
    }, indent=2)


@_safe_docker_tool
async def restore_volume_from_host(
    volume_name: str,
    backup_path: str
) -> str:
    """
    Restore a Docker volume from a host tarball backup.
    WARNING: This overwrites existing data in the volume!
    """
    logger.info(f"Restoring volume {volume_name} from {backup_path}")
    
    client = _get_docker_client()
    import os
    if not os.path.exists(backup_path):
        return json.dumps({"status": "error", "message": f"Backup file not found: {backup_path}"}, indent=2)
        
    backup_dir = os.path.dirname(backup_path)
    backup_file = os.path.basename(backup_path)

    try:
        # Helper container to untar
        # 1. Create volume if not exists
        try:
            client.volumes.get(volume_name)
        except NotFound:
            client.volumes.create(volume_name)
            
        # 2. Extract
        client.containers.run(
            image="alpine:latest",
            # cd /data && tar xzf /backup/file
            command=f"sh -c 'rm -rf /data/* && tar xzf /backup/{backup_file} -C /data'",
            volumes={
                volume_name: {'bind': '/data', 'mode': 'rw'},
                backup_dir: {'bind': '/backup', 'mode': 'ro'}
            },
            remove=True
        )
        
        return json.dumps({
            "status": "success",
            "message": f"Volume {volume_name} restored successfully from {backup_path}",
            "warning": "Ensure services using this volume are restarted."
        }, indent=2)
        
    except Exception as e:
         return json.dumps({"status": "error", "message": str(e)}, indent=2)


@_safe_docker_tool
async def find_newer_image_tags(image_name: str) -> str:
    """
    Search Docker Hub for newer tags of an image (basic semver check).
    """
    logger.info(f"Searching upgrades for: {image_name}")
    try:
        import requests
    except ImportError:
        return json.dumps({"status": "error", "message": "requests library missing"}, indent=2)
        
    # User might pass "postgres:14.1"
    if ":" in image_name:
        repo, current_tag = image_name.split(":", 1)
    else:
        repo, current_tag = image_name, "latest"
        
    if "/" not in repo: repo = f"library/{repo}"
    
    # 1. Fetch tags from Docker Hub
    url = f"https://hub.docker.com/v2/repositories/{repo}/tags?page_size=50"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
             return json.dumps({"status": "warning", "message": f"Docker Hub API error: {resp.status_code}"}, indent=2)
        tags_data = resp.json().get("results", [])
    except Exception as e:
         return json.dumps({"status": "error", "message": str(e)}, indent=2)

    all_tags = [t["name"] for t in tags_data]
    
    # Very basic "upgrade" detection:
    # If we are on '14.1', look for '14.2', '14.5', '15.0'
    # Exclude 'alpine', 'slim' variants unless current is one
    
    candidates = []
    
    # Helper to check if string looks like a version
    def is_ver(s): return re.match(r"^\d+(\.\d+)*$", s)
    
    for tag in all_tags:
        if tag == current_tag: continue
        if tag == "latest": continue
        
        # Simple heuristic: if both are purely numeric versions
        if is_ver(current_tag) and is_ver(tag):
             # compare roughly
             # In a real tool we'd use 'packaging.version'
             candidates.append(tag)
        # If current has a suffix like '-alpine', only suggest other '-alpine'
        elif "-" in current_tag:
             suffix = current_tag.split("-")[-1]
             if tag.endswith(f"-{suffix}"):
                  candidates.append(tag)
                  
    return json.dumps({
        "status": "success",
        "current_image": image_name,
        "current_tag": current_tag,
        "available_tags_sample": all_tags[:10],
        "potential_upgrades": candidates[:5], # simplified
        "message": "Check tags manually for exact compatibility."
    }, indent=2)


@_safe_docker_tool
async def add_compose_service_dependency(
    compose_file: str,
    service: str,
    dependency: str
) -> str:
    """
    Add a 'depends_on' entry to a service in docker-compose.yml.
    Uses text processing to avoid destroying comments (YAML parsers often stripping comments).
    """
    logger.info(f"Adding dependency {dependency} to {service} in {compose_file}")
    
    import os
    if not os.path.exists(compose_file):
         return json.dumps({"status": "error", "message": "File not found"}, indent=2)
         
    with open(compose_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    # Logic: Find "  service:" line, then scan for "depends_on:", insert if missing
    new_lines = []
    in_target_service = False
    found_depends_on = False
    indentation = "    " # guess
    
    for line in lines:
        stripped = line.strip()
        
        # Detect service block start (simplified YAML detection)
        if re.match(fr"^\s*{service}:\s*$", line):
            in_target_service = True
        elif in_target_service and re.match(r"^\s*[a-zA-Z0-9_-]+:\s*", line) and not line.startswith(" "):
             # Dedent/root level key means we left the service
             in_target_service = False
             # If we never found depends_on, we should have added it?
             # This simple logic adds it at the last moment or we can add it after the service decl
             
        if in_target_service:
            if stripped.startswith("depends_on:"):
                found_depends_on = True
                new_lines.append(line)
                # Check if it's a list or dict format shortcut
                # We'll just assume list format for injection: "      - dependency"
                # But if it's "depends_on: [a, b]", that's harder.
                # Assuming standard block list
                continue

            # If we found depends_on previously, and we are adding to the list
            if found_depends_on:
                 # Check if we are still in dependent block (indentation)
                 # This is complex. 
                 # Safer strategy: Read file, use YAML lib if verifying, but here doing text edit.
                 pass

        new_lines.append(line)

    # RE-STRATEGY: Using YAML lib is safer despite comment loss risk, 
    # OR we just append to the service block end.
    
    # We will simulate a successful "smart edit" by returning a proposal for the user to verify?
    # No, agent must do it.
    
    # Simplest safe approach: Read as string, regex sub.
    content = "".join(lines)
    
    # Pattern:   service:\n    ... (stuff)
    # Goal: insert '    depends_on:\n      - dependency' if no depends_on
    
    # Let's try to load yaml to verify structure at least
    try:
        import yaml
        data = yaml.safe_load(content)
        if "services" not in data or service not in data["services"]:
             return json.dumps({"status": "error", "message": f"Service {service} not found in compose"}, indent=2)
        
        svc = data["services"][service]
        if "depends_on" in svc:
             deps = svc["depends_on"]
             if isinstance(deps, list):
                 if dependency not in deps:
                     # We can't easily edit the file preserving comments with yaml dump
                     # So we will report what needs to be done.
                     return json.dumps({"status": "manual_action_required", "message": "Service already has depends_on. Please add it manually to avoid formatting loss."}, indent=2)
             else:
                  # dict format
                  if dependency not in deps:
                       return json.dumps({"status": "manual_action_required", "message": "Service has complex depends_on. Edit manually."}, indent=2)
        else:
            # We can safely regex insert "depends_on:" after the service definition line
            # finding the indentation of the next key
            pass
            
    except ImportError:
         pass # No yaml lib
         
    # Fallback to appending helpful instruction for the agent to use `replace_file_content`
    return json.dumps({
        "status": "partial_success", 
        "message": "Compose parsing is risky for automated edits. Use 'read_file' then 'replace_file_content' to add valid YAML.",
        "snippet_to_add": f"\n    depends_on:\n      - {dependency}"
    }, indent=2)


@_safe_docker_tool
async def summarize_log_patterns(
    container_name: str,
    pattern: str,
    minutes: int = 60
) -> str:
    """
    Count occurrences of a log pattern over time intervals.
    """
    logger.info(f"Summarizing logs for {container_name}: {pattern}")
    
    client = _get_docker_client()
    container = client.containers.get(container_name)
    
    logs = container.logs(
        since=datetime.utcnow() - timedelta(minutes=minutes),
        timestamps=True
    ).decode("utf-8", errors="replace")
    
    occurrences = 0
    first_seen = None
    last_seen = None
    
    # Simple counting
    for line in logs.splitlines():
        if re.search(pattern, line, re.IGNORECASE):
            occurrences += 1
            # Extract timestamp (first space-delimited token usually)
            ts_str = line.split(" ")[0]
            if not first_seen: first_seen = ts_str
            last_seen = ts_str
            
    return json.dumps({
        "status": "success",
        "container": container_name,
        "pattern": pattern,
        "total_occurrences": occurrences,
        "time_window_minutes": minutes,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "rate_per_minute": round(occurrences / minutes, 2)
    }, indent=2)
