from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional
import aiohttp
from pydantic import BaseModel
from NDSPool import NDSPool, PoolConfig
import os

router = APIRouter(prefix="/nds", tags=["NDS"])

# 全局连接池实例
pool = NDSPool()

# 从环境变量获取配置
BACKEND_URL = os.getenv('BACKEND_URL')

class NDSConfig(BaseModel):
    """NDS配置模型"""
    ID: int
    NDSName: str
    Address: str
    Port: int
    Protocol: str
    Account: str
    Password: str
    Status: int
    Switch: int

class ScanRequest(BaseModel):
    """扫描请求模型"""
    nds_id: int
    scan_path: str
    filter_pattern: Optional[str] = None

class ZipInfoRequest(BaseModel):
    """ZIP信息请求模型"""
    nds_id: int
    file_paths: List[str]

class ReadBytesRequest(BaseModel):
    """读取文件请求模型"""
    nds_id: int
    file_path: str
    header_offset: int = 0
    size: Optional[int] = None

async def fetch_nds_configs() -> List[Dict]:
    """从后端获取NDS配置"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BACKEND_URL}/nds/list") as response:
            if response.status == 200:
                data = await response.json()
                return [item for item in data['list'] if item['Switch'] == 1]
    return []

async def init_pool() -> None:
    """初始化连接池"""
    configs = await fetch_nds_configs()
    for config in configs:
        try:
            pool_config = PoolConfig(
                protocol=config['Protocol'],
                host=config['Address'],
                port=config['Port'],
                user=config['Account'],
                passwd=config['Password'],
                pool_size=2
            )
            pool.add_server(str(config['ID']), pool_config)
        except Exception as e:
            print(f"Failed to add NDS {config['ID']}: {str(e)}")

@router.post("/scan")
async def scan_directory(request: ScanRequest) -> List[str]:
    """扫描目录"""
    try:
        async with pool.get_client(str(request.nds_id)) as client:
            return await client.scan(request.scan_path, request.filter_pattern)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/zip-info")
async def get_zip_info(request: ZipInfoRequest) -> Dict[str, List]:
    """获取多个ZIP文件信息
    
    优化：一次获取连接处理多个文件，避免频繁获取释放连接
    """
    try:
        async with pool.get_client(str(request.nds_id)) as client:
            return {
                file_path: await client.get_zip_info(file_path)
                for file_path in request.file_paths
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/read-bytes")
async def read_file_bytes(request: ReadBytesRequest) -> bytes:
    """读取文件内容"""
    try:
        async with pool.get_client(str(request.nds_id)) as client:
            return await client.read_file_bytes(
                request.file_path,
                request.header_offset,
                request.size
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/update-pool")
async def update_pool(action: str, config: Optional[NDSConfig] = None) -> Dict[str, str]:
    """更新连接池配置"""
    try:
        if action == "remove":
            await pool.remove_server(str(config.ID))
            return {"message": "Server removed"}
            
        if not config:
            raise HTTPException(status_code=400, detail="Config is required")
            
        if config.Switch != 1:
            await pool.remove_server(str(config.ID))
            return {"message": "Server removed due to Switch off"}
            
        pool_config = PoolConfig(
            protocol=config.Protocol,
            host=config.Address,
            port=config.Port,
            user=config.Account,
            passwd=config.Password,
            pool_size=2
        )
        
        if action == "add":
            pool.add_server(str(config.ID), pool_config)
        elif action == "update":
            await pool.remove_server(str(config.ID))
            pool.add_server(str(config.ID), pool_config)
            
        return {"message": f"Server {action}ed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 