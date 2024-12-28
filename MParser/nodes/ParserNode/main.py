from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from HttpClient import HttpClient
from config import BACKEND_URL, SERVICE_NAME, SERVICE_HOST, SERVICE_PORT, NODE_TYPE
from api import router
from task_manager import init_processor, shutdown_processor
import multiprocessing
import psutil
import uvicorn


# 获取CPU核心数并计算可用的子进程数
try:
    cpu_threads = len(psutil.Process().cpu_affinity())
except:
    try:
        cpu_threads = multiprocessing.cpu_count()
    except:
        cpu_threads = 2  # 默认假设2线程

# 计算子进程数：
# 1. 为主进程预留一个线程资源
# 2. 剩余线程按每线程2个子进程计算 
# 3. 如果只有2线程，则最多启动2个子进程
cpu_threads = cpu_threads - 1 if cpu_threads > 1 else 1  # 减1是为主进程预留资源
DEFAULT_PROCESSES = cpu_threads * 2 if cpu_threads > 1 else 1

# 创建后端客户端实例
backend_client = None

async def init_api():
    """初始化API"""
    global backend_client
    backend_client = HttpClient(BACKEND_URL)

async def register_node():
    """注册节点"""
    try:
        response = await backend_client.post(
            "node/register",
            json={
                "NodeType": NODE_TYPE,
                "NodeName": SERVICE_NAME,
                "Host": SERVICE_HOST,
                "Port": SERVICE_PORT,
                "Status": "Online"
            }
        )
        
        if response.get("code") != 200:
            raise Exception(response.get("message", "注册失败"))
    except Exception as e:
        print(f"Failed to register node: {e}")
        raise

async def unregister_node():
    """注销节点"""
    try:
        await backend_client.delete(
            "node/unregister",
            json={
                "NodeType": NODE_TYPE,
                "NodeName": SERVICE_NAME
            }
        )
    except Exception as e:
        print(f"Failed to unregister node: {e}")

@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期管理"""
    # 初始化任务处理器
    await init_processor(DEFAULT_PROCESSES)
    # 初始化API客户端并注册节点
    await init_api()
    # await register_node()
    yield
    try:
        await shutdown_processor()
        # await unregister_node()
        await backend_client.close()
    except Exception:
        pass
    

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

app.include_router(router)

if __name__ == "__main__":
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=True
    ) 