from typing import List, Optional
from pydantic import BaseModel, Field

class TaskModel(BaseModel):
    """任务模型"""
    FileHash: str
    NDSID: int
    FilePath: str
    FileTime: str
    SubFileName: str
    HeaderOffset: int = Field(default=0, ge=0)
    CompressSize: int = Field(default=0, ge=0)
    eNodeBID: str = ''
    DataType: str = ''
    FileSize: Optional[int] = None
    FlagBits: Optional[int] = None
    CompressType: Optional[int] = None

class BatchTaskRequest(BaseModel):
    """批量任务请求模型"""
    tasks: List[TaskModel]
