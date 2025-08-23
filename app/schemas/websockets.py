from typing import Any, Literal, Optional
from pydantic import BaseModel


class WSStatusMessage(BaseModel):
    type: Literal["init", "status", "loading", "error"]
    data: Optional[Any] = None
    message: Optional[str] = None


class WSTaskStatusMessage(WSStatusMessage):
    task_id: int
