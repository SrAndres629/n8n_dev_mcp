"""
Data Contracts - Pydantic Models
Defines the structure of data exchanged with n8n API.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class WorkflowNode(BaseModel):
    """Represents a single node in an n8n workflow."""
    id: str
    name: str
    type: str
    position: List[int] = Field(default_factory=lambda: [0, 0])
    parameters: Dict[str, Any] = Field(default_factory=dict)
    typeVersion: float = 1.0


class WorkflowConnections(BaseModel):
    """Represents connections between nodes."""
    # Key: Source node name, Value: Connection details
    connections: Dict[str, Any] = Field(default_factory=dict)


class WorkflowSummary(BaseModel):
    """Lightweight workflow info for listing."""
    id: str
    name: str
    active: bool
    tags: List[str] = Field(default_factory=list)


class WorkflowSpec(BaseModel):
    """Full workflow specification."""
    id: Optional[str] = None
    name: str
    nodes: List[Dict[str, Any]]
    connections: Dict[str, Any]
    active: bool = False
    settings: Dict[str, Any] = Field(default_factory=lambda: {
        "saveManualExecutions": True,
        "saveExecutionProgress": True
    })


class ExecutionError(BaseModel):
    """Details of a failed execution."""
    execution_id: str
    workflow_id: str
    workflow_name: Optional[str] = None
    started_at: Optional[str] = None
    failed_node: str = "Unknown"
    error_message: str = "Unknown Error"


class DeployResult(BaseModel):
    """Result of a workflow deployment."""
    status: str
    action: str  # "created" or "updated"
    id: str
    name: str


class OperationResult(BaseModel):
    """Generic operation result."""
    status: str
    message: str
    workflow_id: Optional[str] = None
