from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv
from HttpClient import HttpClient
import asyncio
from pydantic import BaseModel
import multiprocessing
import psutil
from aiomultiprocess import Pool

# 加载环境变量
load_dotenv()

# 配置
BACKEND_URL = os.getenv('BACKEND_URL')
SERVICE_NAME = os.getenv('SERVICE_NAME')
SERVICE_HOST = os.getenv('SERVICE_HOST')
SERVICE_PORT = int(os.getenv('SERVICE_PORT', 10003))
NODE_TYPE = os.getenv('NODE_TYPE', 'ParserNode')

# 获取CPU核心数
try:
    DEFAULT_PROCESSES = len(psutil.Process().cpu_affinity())
except:
    try:
        DEFAULT_PROCESSES = multiprocessing.cpu_count()
    except:
        DEFAULT_PROCESSES = 4

MAX_PROCESSES = int(os.getenv('MAX_PROCESSES', DEFAULT_PROCESSES))

# 创建后端客户端实例
backend_client = None

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

class NodeStatus:
    """节点状态管理"""
    def __init__(self, max_processes: int):
        self.max_processes = max_processes
        self.active_processes = 0
        self._lock = asyncio.Lock()
        self._pool: Pool = None
        self._tasks = {}  # 存储正在处理的任务

    async def initialize(self):
        """初始化进程池"""
        if self._pool is None:
            self._pool = Pool(self.max_processes)

    async def shutdown(self):
        """关闭进程池"""
        if self._pool:
            await self._pool.close()
            await self._pool.join()
            self._pool = None

    async def increment_active(self) -> bool:
        """增加活动进程数"""
        async with self._lock:
            if self.active_processes >= self.max_processes:
                return False
            self.active_processes += 1
            return True

    async def decrement_active(self):
        """减少活动进程数"""
        async with self._lock:
            if self.active_processes > 0:
                self.active_processes -= 1

    def get_status(self) -> Dict[str, Any]:
        """获取节点状态"""
        return {
            "node_type": NODE_TYPE,
            "node_name": SERVICE_NAME,
            "max_processes": self.max_processes,
            "active_processes": self.active_processes,
            "available_processes": self.max_processes - self.active_processes,
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "tasks_count": len(self._tasks)
        }

    async def notify_task_complete(self, file_hash: str, result: Dict):
        """通知任务完成"""
        try:
            await backend_client.post(
                "nds/task/complete",
                json={
                    "FileHash": file_hash,
                    "NodeName": SERVICE_NAME,
                    "Result": result
                }
            )
        except Exception as e:
            print(f"Failed to notify task completion: {e}")
        finally:
            # 清理任务记录
            self._tasks.pop(file_hash, None)
            await self.decrement_active()

    async def start_task(self, task_data: Dict) -> bool:
        """启动任务处理"""
        if not self._pool:
            raise RuntimeError("Process pool not initialized")

        file_hash = task_data["FileHash"]
        
        # 创建任务处理协程
        async def handle_task():
            try:
                # 这里将是实际的处理函数，现在用sleep模拟
                async def _process(data: Dict) -> Dict:
                    await asyncio.sleep(10)
                    return {
                        "status": "success",
                        "file_hash": data["FileHash"]
                    }

                result = await self._pool.apply(_process, (task_data,))
                await self.notify_task_complete(file_hash, result)
            except Exception as e:
                print(f"Error processing task {file_hash}: {e}")
                await self.notify_task_complete(file_hash, {
                    "status": "error",
                    "error": str(e)
                })

        # 启动任务处理
        task = asyncio.create_task(handle_task())
        self._tasks[file_hash] = task
        return True

# 创建节点状态管理器
node_status = NodeStatus(MAX_PROCESSES)

async def init_api():
    """初始化API"""
    global backend_client
    backend_client = HttpClient(BACKEND_URL)

async def register_node():
    """注册节点"""
    print(f"Registering {NODE_TYPE} {SERVICE_NAME}: {SERVICE_HOST}:{SERVICE_PORT}")
    try:
        await backend_client.post(
            "node/register",
            json={
                "NodeType": NODE_TYPE,
                "NodeName": SERVICE_NAME,
                "Host": SERVICE_HOST,
                "Port": SERVICE_PORT,
                "MaxProcesses": MAX_PROCESSES
            }
        )
        print("Node registered successfully")
    except Exception as e:
        print(f"Failed to register node: {e}")
        raise

async def unregister_node():
    """注销节点"""
    print(f"Unregistering {NODE_TYPE} {SERVICE_NAME}")
    try:
        await backend_client.delete(
            "node/unregister",
            json={
                "NodeType": NODE_TYPE,
                "NodeName": SERVICE_NAME
            }
        )
        print("Node unregistered successfully")
    except Exception as e:
        print(f"Failed to unregister node: {e}")

async def heartbeat():
    """心跳包发送"""
    while True:
        try:
            await backend_client.post(
                "node/heartbeat",
                json={
                    "NodeType": NODE_TYPE,
                    "NodeName": SERVICE_NAME,
                    "Status": node_status.get_status()
                }
            )
        except Exception as e:
            print(f"Failed to send heartbeat: {e}")
        await asyncio.sleep(60)  # 每60秒发送一次心跳

@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期管理"""
    print("Initializing Parser Node...")
    await init_api()
    await node_status.initialize()  # 初始化进程池
    await register_node()
    
    # 启动心跳包任务
    heartbeat_task = asyncio.create_task(heartbeat())
    
    yield
    
    # 停止心跳包任务
    heartbeat_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    
    await node_status.shutdown()  # 关闭进程池
    await unregister_node()
    await backend_client.close()

app = FastAPI(
    title="NDS Parser Node",
    description="NDS 数据解析节点",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
async def root() -> Dict[str, Any]:
    """根路径，返回节点状态"""
    return {
        "code": 200,
        "message": "NDS Parser Node Running",
        "data": node_status.get_status()
    }

@app.get("/status")
async def get_status() -> Dict[str, Any]:
    """获取节点详细状态"""
    return {
        "code": 200,
        "data": node_status.get_status()
    }

@app.post("/task")
async def process_task(task: TaskModel) -> Dict[str, Any]:
    """接收并处理任务"""
    try:
        # 检查是否可以创建新进程
        if not await node_status.increment_active():
            return {
                "code": 503,
                "message": "No available process slots",
                "data": node_status.get_status()
            }

        try:
            # 启动任务处理（不等待完成）
            success = await node_status.start_task(task.dict())
            if not success:
                await node_status.decrement_active()
                return {
                    "code": 500,
                    "message": "Failed to start task",
                    "data": node_status.get_status()
                }

            return {
                "code": 200,
                "message": "Task accepted",
                "data": {
                    "file_hash": task.FileHash,
                    "status": node_status.get_status()
                }
            }

        except Exception as e:
            await node_status.decrement_active()
            raise e

    except Exception as e:
        return {
            "code": 500,
            "message": f"Failed to process task: {str(e)}",
            "data": node_status.get_status()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=True
    ) 