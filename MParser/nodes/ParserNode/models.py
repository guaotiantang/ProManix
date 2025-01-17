from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class TaskModel(BaseModel):
    """任务模型"""
    FileHash: str
    NDSID: int
    FilePath: str
    FileTime: datetime
    SubFileName: str
    HeaderOffset: int = Field(default=0, ge=0)
    CompressSize: int = Field(default=0, ge=0)
    eNodeBID: int = 0
    DataType: str = ''
    FileSize: Optional[int] = None
    FlagBits: Optional[int] = None
    CompressType: Optional[int] = None
    Parsed: int = 0

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class BatchTaskRequest(BaseModel):
    """批量任务请求模型"""
    tasks: List[TaskModel]
