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
