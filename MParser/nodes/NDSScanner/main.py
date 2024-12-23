from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Optional, Any, Union
import os
from dotenv import load_dotenv
from Scanner import scanner  # 导入全局实例
from HttpClient import HttpClient
from fastapi.params import Body

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
    """注销当前服务器的���点记录"""
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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/status")
async def get_status(nds_id: Optional[int] = None) -> Union[Dict[int, Dict], Dict]:
    """获取扫描状态
    
    如果指定nds_id，返回单个NDS的状态
    如果不指定nds_id，返回所有NDS的状态
    """
    status = scanner.get_status(nds_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"NDS {nds_id} not found")
    return status

@app.post("/control")
async def control_scanning(data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """控制扫描服务"""
    try:
        action = data.get('action')
        config = data.get('config', {})
        
        if not action:
            raise HTTPException(status_code=400, detail="Missing action")
            
        if action not in ["add", "update", "remove", "start", "stop"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid action"
            )
            
        # NDS相关操作
        if action in ["add", "update", "remove"]:
            if not config:
                raise HTTPException(
                    status_code=400,
                    detail="Config is required for NDS operations"
                )
            return await scanner.handle_nds_update(action, config)
            
        # 扫描控制操作
        elif action == "start":
            await scanner.start_scanning()
            return {
                "code": 200,
                "message": "Scanning started"
            }
            
        else:  # stop
            nds_id = config.get('ID')  # 可选的NDS ID
            if nds_id:
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
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=True
    )
