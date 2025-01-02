import sys

from fastapi import FastAPI
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os
from NDSApi import router as nds_router, nds_api
from fastapi.middleware.cors import CORSMiddleware
import logging
import uvicorn
# from NDSSocketServer import NDSSocketServer
import asyncio
from fastapi import Body
from NDSClient import NDSClient

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


# # 创建socket服务器实例
# socket_server = NDSSocketServer()

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
                "Port": SERVICE_PORT,
                "Status": "Online"
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
                "NodeName": SERVICE_NAME,
                "Status": "Offline"
            }
        )
    except Exception as e:
        print(f"Failed to unregister node: {e}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期管理"""
    print("等待后端启动")
    await asyncio.sleep(2)  # 等待后端启动完成
    await nds_api.init_api(BACKEND_URL)
    await register_gateway()
    # await socket_server.start()  # 启动socket服务器
    yield
    await unregister_gateway()
    await nds_api.close()
    print("Bye!")
    # await socket_server.stop()   # 停止socket服务器

    sys.exit(0)


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


@app.post("/check")
async def check_nds_connection(config: dict = Body(...)):
    """检查NDS连接配置是否可用

    Args:
        config: NDS配置信息，包含以下字段：
            - Protocol: 协议类型 (FTP/SFTP)
            - Address: 服务器地址
            - Port: 端口号
            - Account: 账号
            - Password: 密码

    Returns:
        Dict: 包含检查结果的字典
            - code: 状态码 (200: 成功, 500: 失败)
            - message: 结果描述
            - data: 详细信息 (可选)
    """
    try:
        # 1. 验证必要字段
        required_fields = ['Protocol', 'Address', 'Port', 'Account', 'Password']
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            return {
                "code": 400,
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }

        # 2. 创建临时客户端进行测试
        client = NDSClient(
            protocol=config['Protocol'],
            host=config['Address'],
            port=int(config['Port']),
            user=config['Account'],
            passwd=config['Password']
        )

        # 3. 尝试连接
        try:
            if await client.connect(3):
                return {
                    "code": 200,
                    "message": "Connection successful",
                    "data": {
                        "status": "connected",
                        "protocol": config['Protocol'],
                        "host": config['Address'],
                        "port": config['Port']
                    }
                }
                
            else:
                return {
                    "code": 500,
                    "message": "Connection check failed",
                    "data": {
                        "status": "disconnected",
                        "reason": "Failed to verify connection"
                    }
                }

        except Exception as e:
            return {
                "code": 500,
                "message": "Connection failed",
                "data": {
                    "status": "error",
                    "error": str(e)
                }
            }

        finally:
            # 5. 确保关闭连接
            await client.close_connect()

    except Exception as e:
        logging.error(f"Check connection error: {str(e)}")
        return {
            "code": 500,
            "message": "Internal server error",
            "error": str(e)
        }


@app.get("/")
async def check_gateway():
    """检查网关状态

    Returns:
        Dict: 包含网关状态信息的字典
            - code: 状态码 (200: 正常)
            - message: 状态描述
            - data: 详细信息
    """
    try:
        return {
            "code": 200,
            "message": "Gateway is running",
            "data": {
                "status": "running",
                "service": SERVICE_NAME,
                "type": NODE_TYPE,
                "host": SERVICE_HOST,
                "port": SERVICE_PORT
            }
        }
    except Exception as e:
        logging.error(f"Gateway status check error: {str(e)}")
        return {
            "code": 500,
            "message": "Gateway error",
            "error": str(e)
        }


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
