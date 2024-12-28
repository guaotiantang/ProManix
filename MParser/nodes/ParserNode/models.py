from typing import List
from pydantic import BaseModel

class TaskModel(BaseModel):
    """任务模型"""
    FileHash: str
    NDSID: int
    FilePath: str
    FileTime: str
    DataType: str
    eNodeBID: int
    SubFileName: str
    HeaderOffset: int
    CompressSize: int
    FileSize: int = None
    FlagBits: int = None
    CompressType: int = None

class BatchTaskRequest(BaseModel):
    """批量任务请求模型"""
    tasks: List[TaskModel]
