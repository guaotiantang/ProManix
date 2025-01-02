import asyncio
from typing import Dict, Any
import dateutil.parser

from fastapi import APIRouter

from SocketClient import LogLevel, SocketClient
from TaskProcess import TaskProcess
from config import NODE_TYPE, SERVICE_NAME
from models import BatchTaskRequest, TaskModel
from config import BACKEND_URL, SERVICE_HOST, SERVICE_PORT

processor: TaskProcess

socket_client: SocketClient

router = APIRouter()


async def get_task():
    """任务获取协程"""
    global socket_client, processor
    while processor.is_running:
        try:
            # 阻塞等待空闲进程
            idle_pid = processor.idle_queue.get()
            if idle_pid is not None:
                # 请求新任务
                if not socket_client.is_connected:
                    await socket_client.connect_to_server()
                result = await socket_client.call_api(
                    api='ndsfile/getTask',
                    data={},
                    callback_type='socket',
                    callback_func='task.receive'
                )
                if not result.get("success"):
                    # 如果获取失败，将进程ID放回空闲队列
                    processor.idle_queue.put(idle_pid)
                    await asyncio.sleep(1)  # 失败后等待一段时间再试
                await asyncio.sleep(0.1)  # 避免过于频繁的请求
        except Exception as e:
            print(f"Error in get_task: {e}")
            await asyncio.sleep(1)



async def init_processor(process_count: int):
    """初始化任务处理器"""
    global processor, socket_client
    processor = TaskProcess(process_count)
    await processor.start()
    socket_client = SocketClient(
        socket_url=f"ws://{BACKEND_URL.replace('http://', '')}",
        http_url=f"{BACKEND_URL}/api/call",
        callback_url=f"http://{SERVICE_HOST}:{SERVICE_PORT}/api/callback",
        options={"log_level": LogLevel.DEBUG}
    )
    socket_client.register_callback(name="task.receive", handler=task_receive)
    await socket_client.connect_to_server()
    asyncio.create_task(get_task())
    





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
    if not isinstance(data, dict) or "data" not in data:
        print(f"Invalid response format: {data}")
        return
        
    response_data = data["data"]
    if not isinstance(response_data, dict) or "code" not in response_data or "data" not in response_data:
        print(f"Invalid inner response format: {response_data}")
        return
        
    if response_data["code"] != 200:
        print(f"Error response: {response_data}")
        return
        
    task_data = response_data["data"]
    if task_data:
        # 转换数据类型
        if isinstance(task_data.get('HeaderOffset'), str):
            task_data['HeaderOffset'] = int(task_data['HeaderOffset'])
        if isinstance(task_data.get('CompressSize'), str):
            task_data['CompressSize'] = int(task_data['CompressSize'])
        if isinstance(task_data.get('FileSize'), str):
            task_data['FileSize'] = int(task_data['FileSize'])
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

