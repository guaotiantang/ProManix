from fastapi import APIRouter
from typing import Dict, Any
from models import BatchTaskRequest
from task_manager import task_queue, processor
from config import NODE_TYPE, SERVICE_NAME

router = APIRouter()

@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """获取节点状态"""
    return {
        "code": 200,
        "data": {
            "node_type": NODE_TYPE,
            "node_name": SERVICE_NAME,
            "available_processes": processor.get_available_processes() if processor else 0
        }
    }

@router.post("/task")
async def process_tasks(request: BatchTaskRequest) -> Dict[str, Any]:
    """接收批量任务"""
    try:
        if not processor or not processor._running:
            return {
                "code": 503,
                "message": "Task processor is not running",
                "data": {
                    "tasks_count": 0
                }
            }

        for task in request.tasks:
            await task_queue.put(task.model_dump())
        
        queue_size = task_queue.qsize()
        
        return {
            "code": 200,
            "message": "Tasks accepted",
            "data": {
                "tasks_count": queue_size
            }
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"Failed to process tasks: {str(e)}",
            "data": {
                "tasks_count": 0
            }
        }
