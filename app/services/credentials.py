"""
Credential Manager Service
Handles creation and management of n8n credentials.
"""
import json
from typing import Dict, Any

from app.core.client import get_client, safe_tool
from app.core.logging import gateway_logger as logger


@safe_tool
async def list_credentials() -> str:
    """
    List all credentials in n8n.
    
    Returns:
        JSON string with list of credentials.
    """
    logger.info("Listing all credentials")
    client = get_client()
    data = await client.get("/credentials")
    return json.dumps(data, indent=2)


@safe_tool
async def get_credential_schema(credential_type: str) -> str:
    """
    Get the JSON schema for a specific credential type.
    
    Args:
        credential_type: The type of credential (e.g. 'postgres', 'telegramApi').
    
    Returns:
        JSON string with the schema definition.
    """
    logger.info(f"Fetching schema for credential type: {credential_type}")
    client = get_client()
    # n8n endpoint for credential definitions/schemas
    # Usually /credential-types/{type}
    try:
        data = await client.get(f"/credential-types/{credential_type}")
        return json.dumps(data, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Could not fetch schema: {str(e)}"
        }, indent=2)


@safe_tool
async def create_credential(name: str, type: str, data_json: str) -> str:
    """
    Create a new credential in n8n.
    
    Args:
        name: Name of the credential.
        type: Type of credential (e.g., 'postgres', 'openaiApi').
        data_json: JSON string containing the credential data (key-value pairs).
    
    Returns:
        JSON string with the created credential details.
    """
    logger.info(f"Creating credential: {name} (Type: {type})")
    
    try:
        data = json.loads(data_json)
    except json.JSONDecodeError as e:
        return json.dumps({
            "status": "error",
            "message": f"Invalid JSON in data_json: {str(e)}"
        }, indent=2)

    payload = {
        "name": name,
        "type": type,
        "data": data
    }
    
    client = get_client()
    # The endpoint might be /credentials or similar. 
    # Based on standard n8n API, it is POST /credentials
    result = await client.post("/credentials", json_data=payload)
    
    logger.info(f"Successfully created credential: {name}")
    
    return json.dumps({
        "status": "success",
        "credential": result
    }, indent=2)
