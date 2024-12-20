import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from HttpClient import HttpClient

logger = logging.getLogger(__name__)

@dataclass
class ScanStatus:
    """扫描状态"""
    last_scan_time: Optional[datetime] = None
    next_scan_time: Optional[datetime] = None
    new_files_count: int = 0
    scan_duration: float = 0.0
    is_scanning: bool = False

class NDSScanner:
    def __init__(self):
        self.backend_client = None
        self.gateway_client = None
        self.scan_interval = 300  # 5分钟
        self.min_interval = 30    # 最小等待时间（秒）
        self.status: Dict[int, ScanStatus] = {}
        self._tasks: Dict[int, asyncio.Task] = {}
        self._running = False
        self._lock = asyncio.Lock()

    async def init_scanner(self, backend_url: str, gateway_url: str):
        """初始化扫描器"""
        self.backend_client = HttpClient(backend_url)
        self.gateway_client = HttpClient(gateway_url)

    async def close(self):
        """关闭资源"""
        if self.backend_client:
            await self.backend_client.close()
        if self.gateway_client:
            await self.gateway_client.close()

    async def fetch_nds_configs(self) -> List[Dict]:
        """获取所有启用的NDS配置"""
        try:
            data = await self.backend_client.get("nds/list")
            if isinstance(data, dict) and 'list' in data:
                return [item for item in data['list'] if item['Switch'] == 1]
            logger.warning(f"Unexpected response format: {data}")
            return []
        except Exception as e:
            logger.error(f"Fetch configs error: {str(e)}")
            return []

    async def scan_nds(self, nds_config: Dict) -> List[str]:
        """扫描单个NDS的文件"""
        try:
            # 扫描MRO文件
            mro_response = await self.gateway_client.post(
                "nds/scan",
                json={
                    "nds_id": nds_config['ID'],
                    "scan_path": nds_config['MRO_Path'],
                    "filter_pattern": nds_config['MRO_Filter']
                }
            )
            mro_files = mro_response if isinstance(mro_response, list) else []

            # 扫描MDT文件
            mdt_response = await self.gateway_client.post(
                "nds/scan",
                json={
                    "nds_id": nds_config['ID'],
                    "scan_path": nds_config['MDT_Path'],
                    "filter_pattern": nds_config['MDT_Filter']
                }
            )
            mdt_files = mdt_response if isinstance(mdt_response, list) else []

            return mro_files + mdt_files
        except Exception as e:
            logger.error(f"Scan error: {str(e)}")
            return []

    async def update_file_list(self, nds_id: int, files: List[str]) -> int:
        """更新文件列表到数据库"""
        try:
            result = await self.backend_client.post(
                "nds/files/sync",
                json={
                    "nds_id": nds_id,
                    "files": files
                }
            )
            # 后端返回的是包含 new_files 的对象
            if isinstance(result, dict):
                return result.get('new_files', 0)
            return 0
        except Exception as e:
            logger.error(f"Update file list error: {str(e)}")
            return 0

    async def scan_loop(self, nds_config: Dict):
        """单个NDS的扫描循环"""
        nds_id = nds_config['ID']
        self.status[nds_id] = ScanStatus()
        
        while self._running:
            try:
                status = self.status[nds_id]
                status.is_scanning = True
                start_time = datetime.now()

                # 执行扫描
                files = await self.scan_nds(nds_config)
                new_files = await self.update_file_list(nds_id, files)

                # 更新状态
                status.last_scan_time = start_time
                scan_duration = (datetime.now() - start_time).total_seconds()
                status.scan_duration = scan_duration
                status.new_files_count = new_files
                
                # 计算下次扫描时间
                wait_time = max(self.min_interval, 
                              self.scan_interval - scan_duration)
                status.next_scan_time = datetime.now().timestamp() + wait_time
                status.is_scanning = False

                await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"Scan error for NDS {nds_id}: {str(e)}")
                self.status[nds_id].is_scanning = False
                await asyncio.sleep(self.min_interval)

    async def handle_nds_update(self, action: str, config: Dict) -> Dict[str, str]:
        """处理NDS配置更新"""
        try:
            async with self._lock:
                nds_id = config['ID']
                
                if action == "remove" or (action == "update" and config['Switch'] == 0):
                    # 停止扫描任务
                    if nds_id in self._tasks:
                        self._tasks[nds_id].cancel()
                        try:
                            await self._tasks[nds_id]
                        except asyncio.CancelledError:
                            pass
                        del self._tasks[nds_id]
                        del self.status[nds_id]
                    return {
                        "code": 200,
                        "message": f"NDS {nds_id} scanning stopped"
                    }
                
                elif action in ["add", "update"] and config['Switch'] == 1:
                    # 如果任务已存在，先停止
                    if nds_id in self._tasks:
                        self._tasks[nds_id].cancel()
                        try:
                            await self._tasks[nds_id]
                        except asyncio.CancelledError:
                            pass
                    
                    # 启动新的扫描任务
                    self._tasks[nds_id] = asyncio.create_task(self.scan_loop(config))
                    return {
                        "code": 200,
                        "message": f"NDS {nds_id} scanning started"
                    }
                
                return {
                    "code": 200,
                    "message": "No action taken"
                }
        except Exception as e:
            logger.error(f"Handle update error: {str(e)}")
            return {
                "code": 500,
                "message": str(e)
            }

    async def start_scanning(self):
        """启动扫描器"""
        async with self._lock:
            if self._running:
                return
            self._running = True
            print("Scanner Started")
            # 获取始配置
            configs = await self.fetch_nds_configs()
            for config in configs:
                if config['Switch'] == 1:
                    self._tasks[config['ID']] = asyncio.create_task(self.scan_loop(config))

    async def stop_scanning(self):
        """停止扫描器"""
        async with self._lock:
            if not self._running:
                return
            self._running = False
            
            tasks = list(self._tasks.values())
            for task in tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self._tasks.clear()
            self.status.clear()
            
            # 关闭HTTP客户端
            await self.backend_client.close()
            await self.gateway_client.close()

    def get_all_status(self) -> Dict[int, Dict]:
        """获取所有NDS的扫描状态"""
        return {
            nds_id: {
                "last_scan_time": status.last_scan_time.isoformat() if status.last_scan_time else None,
                "next_scan_time": status.next_scan_time,
                "new_files_count": status.new_files_count,
                "scan_duration": status.scan_duration,
                "is_scanning": status.is_scanning
            }
            for nds_id, status in self.status.items()
        }

    def get_status(self, nds_id: int) -> Optional[Dict]:
        """获取单个NDS的扫描状态"""
        status = self.status.get(nds_id)
        if not status:
            return None
            
        return {
            "last_scan_time": status.last_scan_time.isoformat() if status.last_scan_time else None,
            "next_scan_time": status.next_scan_time,
            "new_files_count": status.new_files_count,
            "scan_duration": status.scan_duration,
            "is_scanning": status.is_scanning
        } 

# 创建全局实例
scanner = NDSScanner() 