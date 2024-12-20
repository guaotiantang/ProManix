from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Optional, Any
import os
from dotenv import load_dotenv
from scanner import scanner  # 导入全局实例
from HttpClient import HttpClient

# 加载环境变量
load_dotenv()

# 配置
BACKEND_URL = os.getenv('BACKEND_URL')
GATEWAY_URL = os.getenv('GATEWAY_URL')
SERVICE_NAME = os.getenv('SERVICE_NAME')
SERVICE_HOST = os.getenv('SERVICE_HOST')
SERVICE_PORT = int(os.getenv('SERVICE_PORT', 10002))
NODE_TYPE = os.getenv('NODE_TYPE', 'NDSScanner')

# 创建后端客户端实例
backend_client = None

async def init_api():
    """初始化API"""
    global backend_client
    backend_client = HttpClient(BACKEND_URL)

# 注册节点
async def register_node():
    """注册当前服务器为扫描节点"""
    print(f"Registering {NODE_TYPE} {SERVICE_NAME}: {SERVICE_HOST}:{SERVICE_PORT}")
    try:
        await backend_client.post(
            "node/register",
            json={
                "NodeType": NODE_TYPE,
                "NodeName": SERVICE_NAME,
                "Host": SERVICE_HOST,
                "Port": SERVICE_PORT
            }
        )
    except Exception as e:
        print(f"Failed to register node: {e}")

# 注销节点
async def unregister_node():
    """注销当前服务器的节点记录"""
    print(f"Unregistering {NODE_TYPE} {SERVICE_NAME}")
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
    await init_api()  # 初始化API
    await scanner.init_scanner(BACKEND_URL, GATEWAY_URL)  # 初始化扫描器
    await register_node()  # 注册节点
    await scanner.start_scanning()  # 启动扫描器
    yield
    await scanner.stop_scanning()  # 停止扫描器
    await unregister_node()  # 注销节点
    await scanner.close()  # 关闭扫描器
    await backend_client.close()  # 关闭API客户端
    os._exit(0)

app = FastAPI(
    title="NDS Scanner Service",
    description="NDS文件扫描服务",
    version="1.0.0",
    lifespan=lifespan
)

# 跨域设置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/status")
async def get_status(nds_id: Optional[int] = None) -> Dict[str, Any]:
    """获取扫描状态"""
    try:
        if nds_id is not None:
            status = scanner.get_status(nds_id)
            if status is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"NDS {nds_id} not found"
                )
            return {
                "code": 200,
                "data": {
                    "nds_id": nds_id,
                    "status": status
                }
            }
        else:
            return {
                "code": 200,
                "data": scanner.get_all_status()
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/control/{action}")
async def control_scanning(
    action: str,
    nds_id: Optional[int] = None
) -> Dict[str, Any]:
    """控制扫描服务"""
    if action not in ["start", "stop"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid action. Must be 'start' or 'stop'"
        )
    
    try:
        if action == "start":
            if nds_id is not None:
                raise HTTPException(
                    status_code=400,
                    detail="Start action cannot be applied to single NDS"
                )
            await scanner.start_scanning()
            return {
                "code": 200,
                "message": "Scanning started"
            }
        else:  # stop
            if nds_id is not None:
                await scanner.stop_nds_scan(nds_id)
                return {
                    "code": 200,
                    "message": f"NDS {nds_id} scanning stopped"
                }
            else:
                await scanner.stop_scanning()
                return {
                    "code": 200,
                    "message": "All scanning stopped"
                }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/control/nds")
async def handle_nds_update(action: str, config: Dict) -> Dict[str, str]:
    """处理NDS配置更新"""
    return await scanner.handle_nds_update(action, config)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=True
    )
