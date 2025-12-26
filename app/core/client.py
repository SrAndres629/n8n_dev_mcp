"""
HTTP Client Layer - Singleton Pattern
Provides a robust, reusable async HTTP client with global error handling.
"""
import httpx
import json
from typing import Any, Dict, Optional
from functools import wraps

from app.core.config import settings


class N8NClientError(Exception):
    """Custom exception for n8n API errors."""
    def __init__(self, status_code: int, message: str, context: str = ""):
        self.status_code = status_code
        self.message = message
        self.context = context
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": "error",
            "code": self.status_code,
            "message": self.message,
            "context": self.context
        }


class N8NClient:
    """
    Singleton HTTP Client for n8n API.
    Manages connection lifecycle, headers, and error handling.
    """
    _instance: Optional["N8NClient"] = None
    _client: Optional[httpx.AsyncClient] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:

            self._base_url = settings.n8n_base_url
            self._headers = {
                "X-N8N-API-KEY": settings.n8n_api_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            self._timeout = httpx.Timeout(settings.http_timeout, read=60.0)
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                headers=self._headers,
                timeout=self._timeout
            )

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    async def close(self):
        """Close the HTTP client connection."""
        if self._client:
            await self._client.aclose()
            self._client = None
            N8NClient._instance = None

    async def request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Execute an HTTP request with standardized error handling.
        """
        try:
            response = await self._client.request(
                method=method,
                url=endpoint,
                json=json_data,
                params=params
            )
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_detail = e.response.json()
            except Exception:
                error_detail = e.response.text
            raise N8NClientError(
                status_code=e.response.status_code,
                message=f"n8n API Error: {error_detail}",
                context=str(e)
            )

        except httpx.RequestError as e:
            raise N8NClientError(
                status_code=503,
                message="Network/Connection Failure",
                context=str(e)
            )

    # Convenience methods
    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        return await self.request("GET", endpoint, params=params)

    async def post(self, endpoint: str, json_data: Optional[Dict] = None) -> Dict[str, Any]:
        return await self.request("POST", endpoint, json_data=json_data)

    async def put(self, endpoint: str, json_data: Optional[Dict] = None) -> Dict[str, Any]:
        return await self.request("PUT", endpoint, json_data=json_data)

    async def delete(self, endpoint: str) -> Dict[str, Any]:
        return await self.request("DELETE", endpoint)


def get_client() -> N8NClient:
    """Factory function to get the singleton client instance."""
    return N8NClient()


def safe_tool(func):
    """
    Decorator for MCP tools.
    Catches N8NClientError and returns JSON error response instead of crashing.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except N8NClientError as e:
            return json.dumps(e.to_dict(), indent=2)
        except ValueError as e:
            return json.dumps({
                "status": "error",
                "code": 400,
                "message": f"Validation Error: {str(e)}"
            }, indent=2)
        except Exception as e:
            return json.dumps({
                "status": "fatal_error",
                "code": 500,
                "message": f"Internal MCP Error: {str(e)}"
            }, indent=2)
    return wrapper
