"""
Package Manager Service - Dependency Management
Handles installation of community nodes via npm.
"""
import json
import subprocess
import os
from typing import Optional, List

from app.core.config import settings
from app.core.client import safe_tool
from app.core.logging import packages_logger as logger


def _get_n8n_custom_dir() -> str:
    """Get the path to n8n's custom nodes directory."""
    return os.path.join(settings.n8n_data_dir, "custom")


def _ensure_custom_dir_exists():
    """Create the custom nodes directory if it doesn't exist."""
    custom_dir = _get_n8n_custom_dir()
    if not os.path.exists(custom_dir):
        os.makedirs(custom_dir)
        logger.info(f"Created custom nodes directory: {custom_dir}")
    return custom_dir


@safe_tool
async def install_community_node(package_name: str, version: Optional[str] = None) -> str:
    """
    Install a community node package via npm.
    
    Args:
        package_name: Name of the npm package (e.g., 'n8n-nodes-browserless')
        version: Optional specific version to install
    
    Returns:
        JSON string with installation result.
    """
    custom_dir = _ensure_custom_dir_exists()
    
    # Build package spec
    package_spec = f"{package_name}@{version}" if version else package_name
    
    logger.info(f"Installing community node: {package_spec}")
    logger.info(f"Installation directory: {custom_dir}")
    
    try:
        # Initialize package.json if it doesn't exist
        package_json = os.path.join(custom_dir, "package.json")
        if not os.path.exists(package_json):
            logger.info("Initializing package.json in custom directory")
            init_result = subprocess.run(
                ["npm", "init", "-y"],
                cwd=custom_dir,
                capture_output=True,
                text=True,
                shell=True
            )
            if init_result.returncode != 0:
                raise RuntimeError(f"npm init failed: {init_result.stderr}")
        
        # Install the package
        result = subprocess.run(
            ["npm", "install", package_spec, "--save"],
            cwd=custom_dir,
            capture_output=True,
            text=True,
            shell=True,
            timeout=120  # 2 minute timeout
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully installed: {package_spec}")
            return json.dumps({
                "status": "success",
                "package": package_name,
                "version": version or "latest",
                "install_path": custom_dir,
                "output": result.stdout[-500:] if result.stdout else "",
                "restart_required": True,
                "restart_message": "⚠️ Restart n8n to load the new node. Run: n8n restart (or restart the Docker container)"
            }, indent=2)
        else:
            logger.error(f"Installation failed: {result.stderr}")
            return json.dumps({
                "status": "error",
                "package": package_name,
                "error": result.stderr[-500:] if result.stderr else "Unknown error",
                "return_code": result.returncode
            }, indent=2)
            
    except subprocess.TimeoutExpired:
        logger.error(f"Installation timed out for: {package_name}")
        return json.dumps({
            "status": "error",
            "package": package_name,
            "error": "Installation timed out after 120 seconds"
        }, indent=2)
    except Exception as e:
        logger.error(f"Installation error: {str(e)}")
        return json.dumps({
            "status": "error",
            "package": package_name,
            "error": str(e)
        }, indent=2)


@safe_tool
async def uninstall_community_node(package_name: str) -> str:
    """
    Uninstall a community node package.
    
    Args:
        package_name: Name of the npm package to uninstall
    
    Returns:
        JSON string with uninstall result.
    """
    custom_dir = _get_n8n_custom_dir()
    
    if not os.path.exists(custom_dir):
        return json.dumps({
            "status": "error",
            "error": "Custom nodes directory does not exist"
        }, indent=2)
    
    logger.info(f"Uninstalling community node: {package_name}")
    
    try:
        result = subprocess.run(
            ["npm", "uninstall", package_name, "--save"],
            cwd=custom_dir,
            capture_output=True,
            text=True,
            shell=True,
            timeout=60
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully uninstalled: {package_name}")
            return json.dumps({
                "status": "success",
                "package": package_name,
                "restart_required": True
            }, indent=2)
        else:
            return json.dumps({
                "status": "error",
                "package": package_name,
                "error": result.stderr
            }, indent=2)
            
    except Exception as e:
        return json.dumps({
            "status": "error",
            "package": package_name,
            "error": str(e)
        }, indent=2)


@safe_tool
async def list_installed_nodes() -> str:
    """
    List all installed community nodes.
    
    Returns:
        JSON string with list of installed packages.
    """
    custom_dir = _get_n8n_custom_dir()
    
    if not os.path.exists(custom_dir):
        return json.dumps({
            "status": "success",
            "packages": [],
            "message": "No custom nodes directory found"
        }, indent=2)
    
    package_json = os.path.join(custom_dir, "package.json")
    
    if not os.path.exists(package_json):
        return json.dumps({
            "status": "success",
            "packages": [],
            "message": "No packages installed"
        }, indent=2)
    
    try:
        with open(package_json, "r") as f:
            pkg_data = json.load(f)
        
        dependencies = pkg_data.get("dependencies", {})
        packages = [
            {"name": name, "version": version}
            for name, version in dependencies.items()
        ]
        
        logger.info(f"Found {len(packages)} installed community nodes")
        
        return json.dumps({
            "status": "success",
            "packages": packages,
            "install_path": custom_dir
        }, indent=2)
        
    except Exception as e:
        return json.dumps({
            "status": "error",
            "error": str(e)
        }, indent=2)


@safe_tool
async def get_n8n_info() -> str:
    """
    Get information about the n8n installation and configuration.
    
    Returns:
        JSON string with n8n configuration details.
    """
    info = {
        "base_url": settings.n8n_base_url,
        "editor_url": settings.n8n_editor_url,
        "data_dir": settings.n8n_data_dir,
        "custom_nodes_dir": _get_n8n_custom_dir(),
        "data_dir_exists": os.path.exists(settings.n8n_data_dir),
        "custom_dir_exists": os.path.exists(_get_n8n_custom_dir())
    }
    
    return json.dumps(info, indent=2)
