from fastapi import APIRouter, HTTPException, Body
from typing import Dict, List, Optional
from NDSPool import NDSPool, PoolConfig
from HttpClient import HttpClient, HttpConfig
import os
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nds", tags=["NDS"])

class NDSApi:
    def __init__(self):
        self.pool = NDSPool()
        self.backend_client = None

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
async def update_pool(action: str, config: Dict) -> Dict[str, str]:
    """更新连接池配置"""
    try:
        if action == "remove":
            await nds_api.pool.remove_server(str(config['ID']))
            return {"message": "Server removed"}
            
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
            
        async with nds_api.pool.get_client(str(nds_id)) as client:
            print(f"scan nds {nds_id}")
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