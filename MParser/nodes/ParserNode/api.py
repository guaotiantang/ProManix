from fastapi import APIRouter, Request
from typing import Dict, Any
from models import BatchTaskRequest
from TaskProcess import TaskProcess
from config import NODE_TYPE, SERVICE_NAME

processor: TaskProcess

router = APIRouter()


async def init_processor(process_count: int):
    """初始化任务处理器"""
    global processor
    processor = TaskProcess(process_count)
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

        # 将任务放入队列
        for task in request.tasks:
            processor.queue.put_nowait(task.model_dump())

        return {
            "code": 200,
            "message": f"Accepted {len(request.tasks)} tasks"
        }
    except Exception as e:
        return {
            "code": 500,
            "message": f"Failed to process tasks: {str(e)}",
        }
