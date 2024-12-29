from fastapi import APIRouter, Request
from typing import Dict, Any
from models import BatchTaskRequest
from task_manager import TaskProcessor
from config import NODE_TYPE, SERVICE_NAME

processor = TaskProcessor(2)

router = APIRouter()


async def init_processor(process_count: int):
    """初始化任务处理器"""
    processor.process_count = process_count
    await processor.start()
    

async def shutdown_processor():
    """关闭任务处理器"""
    if processor:
        await processor.stop()




@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """获取节点状态"""
    if not processor:
        return {
            "code": 503,
            "data": {
                "node_type": NODE_TYPE,
                "node_name": SERVICE_NAME,
                "available_processes": 0,
                "status": "Not Ready"
            }
        }
        
    return {
        "code": 200,
        "data": {
            "node_type": NODE_TYPE,
            "node_name": SERVICE_NAME,
            "available_processes": processor.get_available_processes(),
            "status": "Ready"
        }
    }

@router.post("/task")
async def process_tasks(request: Request) -> Dict[str, Any]:
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

        # 打印原始请求数据
        body = await request.json()
        tasks = body.get('tasks', [])
        print(f"Received {len(tasks)} tasks")
        
        # 将任务放入队列
        for i, task in enumerate(tasks):
            # 确保所有必需字段都存在
            required_fields = ['FileHash', 'NDSID', 'FilePath', "SubFileName", 'FileTime', "HeaderOffset", "CompressSize", "eNodeBID"]
            missing_fields = [field for field in required_fields if field not in task]
            if missing_fields:
                raise ValueError(f"Missing required fields: {missing_fields}")
                
            # 转换数字类型
            if 'NDSID' in task:
                task['NDSID'] = int(task['NDSID'])
            if 'eNodeBID' in task:
                task['eNodeBID'] = int(task.get('eNodeBID', 0))
            if 'HeaderOffset' in task:
                task['HeaderOffset'] = int(task.get('HeaderOffset', 0))
            if 'CompressSize' in task:
                task['CompressSize'] = int(task.get('CompressSize', 0))
                
            # 使用processor的队列
            processor.put_task(task)
        
        status = processor.get_process_status()
        print(f"Current status - Queue: {status['queue_size']}, Active: {status['active_processes']}, Available: {status['available_processes']}")
        
        # 立即返回成功响应
        return {
            "code": 200,
            "message": "Tasks accepted",
            "data": {
                "tasks_count": len(tasks),
                "queue_size": status["queue_size"],
                "active_processes": status["active_processes"],
                "available_processes": status["available_processes"]
            }
        }
    except Exception as e:
        print(f"Error processing tasks: {str(e)}")
        print(f"Error type: {type(e)}")
        return {
            "code": 500,
            "message": f"Failed to process tasks: {str(e)}",
            "data": {
                "tasks_count": 0
            }
        }
