from fastapi import FastAPI
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
from NDSApi import router as nds_router, nds_api
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn

# 配置日志
logging.getLogger("uvicorn.access").disabled = True  # 禁用访问日志
logging.getLogger("uvicorn.error").propagate = False  # 防止错误日志重复
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 加载环境变量
load_dotenv()

# 从环境变量获取配置
BACKEND_URL = os.getenv('BACKEND_URL')
SERVICE_NAME = os.getenv('SERVICE_NAME')
SERVICE_HOST = os.getenv('SERVICE_HOST')
SERVICE_PORT = int(os.getenv('SERVICE_PORT', 10001))
NODE_TYPE = os.getenv('NODE_TYPE', 'NDSGateway')

# 注册网关
async def register_gateway():
    """注册当前服务器为网关"""
    print(f"Registering {NODE_TYPE} {SERVICE_NAME}: {SERVICE_HOST}:{SERVICE_PORT}")
    try:
        await nds_api.backend_client.post(
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

# 注销网关
async def unregister_gateway():
    """注销当前服务器的网关记录"""
    print(f"Unregistering {NODE_TYPE} {SERVICE_NAME}")
    try:
        await nds_api.backend_client.delete(
            "node/unregister",
            json={
                "NodeType": NODE_TYPE,
                "NodeName": SERVICE_NAME
            }
        )
    except Exception as e:
        print(f"Failed to unregister node: {e}")
    os._exit(0)

@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期管理"""
    await nds_api.init_api(BACKEND_URL)
    await register_gateway()
    yield
    await unregister_gateway()
    await nds_api.close()
    os._exit(0)

app = FastAPI(
    title="NDS Client Pool Manager",
    description="NDS客户端连接池管理服务",
    version="1.0.0",
    lifespan=lifespan
)

#  跨域访问
# noinspection PyTypeChecker
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# 注册路由
app.include_router(nds_router)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=True,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": "uvicorn.logging.DefaultFormatter",
                    "fmt": "%(asctime)s - %(levelname)s - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": "WARNING"},
                "uvicorn.error": {"level": "ERROR"},
                "uvicorn.access": {"handlers": ["default"], "level": "ERROR", "propagate": False},
            },
        }
    )

