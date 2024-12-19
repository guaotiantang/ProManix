from fastapi import FastAPI
from contextlib import asynccontextmanager
import aiohttp
from dotenv import load_dotenv
import os
from NDSApi import router as nds_router, init_pool, pool

# 加载环境变量
load_dotenv()

# 从环境变量获取配置
BACKEND_URL = os.getenv('BACKEND_URL')
SERVICE_HOST = os.getenv('SERVICE_HOST')
SERVICE_PORT = int(os.getenv('SERVICE_PORT', 10001))

# 注册网关
async def register_gateway():
    """注册当前服务器为网关"""
    print(f"Registering gateway: {SERVICE_HOST}:{SERVICE_PORT}")
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(
                f"{BACKEND_URL}/gateway/add",
                json={"Host": SERVICE_HOST, "Port": SERVICE_PORT}
            )
        except Exception as e:
            print(f"Failed to register gateway: {e}")

# 注销网关
async def unregister_gateway():
    """注销当前服务器的网关记录"""
    async with aiohttp.ClientSession() as session:
        print(f"Unregistering gateway: {SERVICE_HOST}:{SERVICE_PORT}")
        try:
            await session.delete(
                f"{BACKEND_URL}/gateway/remove",
                json={"Host": SERVICE_HOST, "Port": SERVICE_PORT}
            )
        except Exception as e:
            print(f"Failed to unregister gateway: {e}")

@asynccontextmanager
async def lifespan(_: FastAPI):
    """应用生命周期管理"""
    await init_pool()
    await register_gateway()
    yield
    await unregister_gateway()
    await pool.close()

app = FastAPI(
    title="NDS Client Pool Manager",
    description="NDS客户端连接池管理服务",
    version="1.0.0",
    lifespan=lifespan
)

# 注册路由
app.include_router(nds_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=SERVICE_PORT,
        reload=True
    )

