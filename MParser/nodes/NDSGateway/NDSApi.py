from fastapi import APIRouter, HTTPException, Body
from typing import Dict, List, Optional, Any
from NDSPool import NDSPool, PoolConfig
from HttpClient import HttpClient, HttpConfig
import os
import logging
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nds", tags=["NDS"])

class NDSApi:
    def __init__(self):
        self.pool = NDSPool()
        self.backend_client = None
        self.scan_semaphore = asyncio.Semaphore(100)

    async def init_api(self, backend_url: str):
        """初始化API"""
        self.backend_client = HttpClient(backend_url)
        await self.init_pool()

    async def init_pool(self):
        """初始化连接池"""
        try:
            data = await self.backend_client.get("nds/list")
            if not data:
                return
                
            for nds in data.get('list', []):
                if nds['Switch'] == 1:
                    pool_config = PoolConfig(
                        protocol=nds['Protocol'],
                        host=nds['Address'],
                        port=nds['Port'],
                        user=nds['Account'],
                        passwd=nds['Password']
                    )
                    self.pool.add_server(str(nds['ID']), pool_config)
                    print(f"add pool nds[{nds['ID']}]")
        except Exception as e:
            logger.error(f"Failed to initialize pool: {e}")

    async def close(self):
        """关闭资源"""
        await self.pool.close()
        if self.backend_client:
            await self.backend_client.close()

# 创建全局实例
nds_api = NDSApi()

@router.post("/update-pool")
async def update_pool(
    action: str,
    config: Dict[str, Any]
) -> Dict[str, str]:
    """更新连接池配置"""
    try:
        if not isinstance(config, dict):
            raise HTTPException(status_code=400, detail="Invalid config format")
            
        if action == "remove":
            if 'ID' not in config:
                raise HTTPException(status_code=400, detail="Missing ID in config")
            await nds_api.pool.remove_server(str(config['ID']))
            return {"message": "Server removed"}
            
        required_fields = ['ID', 'Switch', 'Protocol', 'Address', 'Port', 'Account', 'Password']
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
            
        if config['Switch'] != 1:
            await nds_api.pool.remove_server(str(config['ID']))
            return {"message": "Server removed due to Switch off"}
            
        pool_config = PoolConfig(
            protocol=config['Protocol'],
            host=config['Address'],
            port=config['Port'],
            user=config['Account'],
            passwd=config['Password']
        )
        
        if action == "add":
            nds_api.pool.add_server(str(config['ID']), pool_config)
        elif action == "update":
            await nds_api.pool.remove_server(str(config['ID']))
            nds_api.pool.add_server(str(config['ID']), pool_config)
        else:
            raise HTTPException(status_code=400, detail="Invalid action")
            
        return {"message": f"Server {action}ed successfully"}
    except Exception as e:
        logger.error(f"Update pool error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scan")
async def scan_files(data: dict = Body(...)) -> List[str]:
    """扫描文件"""
    try:
        nds_id = data.get('nds_id')
        scan_path = data.get('scan_path')
        filter_pattern = data.get('filter_pattern')
        
        if not nds_id or not scan_path:
            raise HTTPException(status_code=400, detail="Missing required parameters")
            
        async with nds_api.scan_semaphore:
            async with nds_api.pool.get_client(str(nds_id)) as client:
                return await client.scan(scan_path, filter_pattern)
    except Exception as e:
        logger.error(f"Scan files error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_pool_status() -> Dict:
    """获取连接池状态"""
    try:
        return nds_api.pool.get_all_pool_status()
    except Exception as e:
        logger.error(f"Get pool status error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/zip-info")
async def get_zip_info(data: dict = Body(...)) -> Dict[str, Any]:
    """获取多个ZIP文件的信息"""
    try:
        nds_id = data.get('nds_id')
        file_paths = data.get('file_paths', [])
        
        if not nds_id or not file_paths:
            raise HTTPException(status_code=400, detail="Missing required parameters")
            
        async with nds_api.scan_semaphore:
            async with nds_api.pool.get_client(str(nds_id)) as client:
                # 串行处理每个文件
                zip_infos = {}
                for file_path in file_paths:
                    try:
                        result = await client.get_zip_info(file_path)
                        zip_infos[file_path] = {
                            "status": "success",
                            "info": [
                                {
                                    "file_name": info.file_name,
                                    "sub_file_name": info.sub_file_name,
                                    "directory": info.directory,
                                    "compress_size": info.compress_size,
                                    "file_size": info.file_size,
                                    "enodebid": getattr(info, 'enodebid', None)
                                }
                                for info in result
                            ]
                        }
                    except Exception as e:
                        zip_infos[file_path] = {
                            "status": "error",
                            "error": str(e)
                        }
                        logger.error(f"Error processing {file_path}: {e}")
                
                return {
                    "code": 200,
                    "data": zip_infos
                }
                
    except Exception as e:
        logger.error(f"Get ZIP info error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 