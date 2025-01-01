from typing import Dict, Any
from datetime import datetime
import dateutil.parser

from fastapi import APIRouter

from SocketClient import SocketClient
from TaskProcess import TaskProcess
from config import NODE_TYPE, SERVICE_NAME
from models import BatchTaskRequest, TaskModel

processor: TaskProcess

router = APIRouter()


async def init_processor(process_count: int, socket_client: SocketClient):
    """初始化任务处理器"""
    global processor
    processor = TaskProcess(process_count, socket_client)
    await processor.start()


async def shutdown_processor():
    """关闭任务处理器"""
    global processor
    if processor:
        await processor.stop()


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """获取节点状态"""
    global processor
    return {
        "code": 200,
        "data": {
            "node_type": NODE_TYPE,
            "node_name": SERVICE_NAME,
            "idle_process_count": processor.idle_process_count
        }
    }


async def task_receive(data: Dict[str, Any]):
    """处理任务接收"""
    if not data:
        return
        
    # 检查响应格式
    if not isinstance(data, dict) or "code" not in data or "data" not in data:
        print(f"Invalid response format: {data}")
        return
        
    if data["code"] != 200:
        print(f"Error response: {data}")
        return
        
    task_data = data["data"]
    if task_data:
        await process_tasks(BatchTaskRequest(tasks=[TaskModel(**task_data)]))


@router.post("/task")
async def process_tasks(request: BatchTaskRequest) -> Dict[str, Any]:
    """接收批量任务"""
    global processor
    try:
        if not processor or not processor.is_running:
            return {
                "code": 503,
                "message": "Task processor is not running",
            }

        for task_data in request.tasks:
            # 数据预处理
            task_dict = task_data.model_dump()
            
            # 处理时间格式
            if isinstance(task_dict["FileTime"], str):
                try:
                    task_dict["FileTime"] = dateutil.parser.parse(task_dict["FileTime"])
                except Exception as e:
                    print(f"Error parsing date: {task_dict['FileTime']}, error: {e}")
                    pass
            
            # 确保eNodeBID是整数
            if "eNodeBID" in task_dict:
                task_dict["eNodeBID"] = int(task_dict["eNodeBID"])
            
            # 处理大整数
            for field in ["HeaderOffset", "CompressSize", "FileSize"]:
                if field in task_dict and task_dict[field] is not None:
                    task_dict[field] = int(task_dict[field])

            processor.task_queue.put_nowait(task_dict)

        return {
            "code": 200,
            "message": f"Accepted {len(request.tasks)} tasks"
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"Failed to process tasks: {str(e)}",
        }

