import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from HttpClient import HttpClient
import re

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
        # 预编译正则表达式
        self._time_pattern = re.compile(r'[_-](\d{14})')

    def _extract_time_from_name(self, name: str) -> str:
        """从文件名中提取时间并转换为数据库格式
        
        Args:
            name: 文件名，支持以下格式：
                 - FDD-LTE_MRO_ZTE_OMC1_292551_20241220023000.zip
                 - FDD-LTE_MRO_ZTE_OMC1_292551-20241220023000_1.zip
                 等任意包含 _YYYYMMDDHHMMSS 或 -YYYYMMDDHHMMSS 的格式
        
        Returns:
            str: 格式化的时间字符串，如 '2024-12-20 02:30:00'
                 如果无法提取时间，返回当前时间
        """
        try:
            match = self._time_pattern.search(name)
            if match:
                time_str = match.group(1)
                # 解析时间字符串
                parsed_time = datetime.strptime(time_str, '%Y%m%d%H%M%S')
                # 转换为数据库格式
                return parsed_time.strftime('%Y-%m-%d %H:%M:%S')
        except Exception as e:
            logger.warning(f"Failed to parse time from name {name}: {e}")
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

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

    async def scan_nds(self, nds_config: Dict) -> List[Dict]:
        """扫描单个NDS的文件"""
        try:
            # 扫描MRO文件
            mro_response = await self.gateway_client.post(
                "nds/scan",
                json={
                    "nds_id": nds_config['ID'],
                    "scan_path": nds_config['MRO_Path'],
                    "filter_pattern": nds_config['MRO_Filter'],
                    "data_type": "MRO"  # 添加文件类型标记
                }
            )
            mro_files = [{"path": f, "type": "MRO"} for f in (mro_response if isinstance(mro_response, list) else [])]

            # 扫描MDT文件
            mdt_response = await self.gateway_client.post(
                "nds/scan",
                json={
                    "nds_id": nds_config['ID'],
                    "scan_path": nds_config['MDT_Path'],
                    "filter_pattern": nds_config['MDT_Filter'],
                    "data_type": "MDT"  # 添加文件类型标记
                }
            )
            mdt_files = [{"path": f, "type": "MDT"} for f in (mdt_response if isinstance(mdt_response, list) else [])]

            return mro_files + mdt_files
        except Exception as e:
            logger.error(f"Scan error: {str(e)}")
            return []

    async def parse_zip_info(self, nds_id: int, files: List[Dict]) -> List[Dict]:
        """解析zip文件信息，返回符合NDSFileList格式的数据"""
        try:
            result = await self.gateway_client.post(
                "nds/zip-info",
                json={
                    "nds_id": nds_id,
                    "file_paths": [file['FilePath'] for file in files]
                }
            )

            # 处理结果
            zip_infos = []
            if isinstance(result, dict) and 'data' in result:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                for file_path, info in result['data'].items():
                    if info['status'] == 'success':
                        file_data = next((f for f in files if f['FilePath'] == file_path), None)
                        if file_data:
                            for file_info in info['info']:
                                # 优先从SubFileName提取时间，如果失败则尝试从FilePath提取
                                file_time = (
                                    self._extract_time_from_name(file_info['sub_file_name']) 
                                    if file_info.get('sub_file_name') 
                                    else self._extract_time_from_name(file_path)
                                )
                                
                                zip_info = {
                                    'NDSID': nds_id,
                                    'FilePath': file_path,
                                    'FileTime': file_time,
                                    'DataType': file_data['DataType'],
                                    'eNodeBID': int(file_info.get('enodebid', 0)),
                                    'SubFileName': file_info['sub_file_name'],
                                    'HeaderOffset': file_info.get('header_offset', 0),
                                    'CompressSize': file_info['compress_size'],
                                    'FileSize': file_info['file_size'],
                                    'FlagBits': file_info.get('flag_bits', 0),
                                    'CompressType': file_info.get('compress_type', 0),
                                    'Parsed': 0, # 0:未解析
                                    'CreateTime': current_time,
                                    'UpdateTime': current_time
                                }
                                zip_infos.append(zip_info)
            
            return zip_infos
        except Exception as e:
            logger.error(f"Parse ZIP info error: {str(e)}")
            return []

    async def diff_files(self, nds_id: int, files: List[Dict]) -> List[Dict]:
        """获取新增文件信息列表"""
        try:
            # 修改请求格式，直接发送包含 path 和 type 的文件列表
            result = await self.backend_client.post(
                "nds/files/diff",
                json={
                    "nds_id": nds_id,
                    "files": [
                        {
                            "path": file["path"],
                            "type": file["type"]
                        } for file in files
                    ]
                }
            )
            
            if isinstance(result, dict) and 'new_files' in result:
                # 不需要额外处理类型信息，因为后端已经返回了完整的信息
                return result['new_files']
            return []
        except Exception as e:
            logger.error(f"Diff files error: {str(e)}")
            return []

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
                new_files = await self.diff_files(nds_id, files)

                # 更新状态
                status.last_scan_time = start_time
                status.scan_duration = (datetime.now() - start_time).total_seconds()
                status.new_files_count = len(new_files)
                
                # 处理新文件
                if new_files:
                    semaphore = asyncio.Semaphore(2)
                    # 直接使用 new_files，因为它们已经包含了类型信息
                    batches = [new_files[i:i + 10] for i in range(0, len(new_files), 10)]
                    
                    results = await asyncio.gather(*(
                        self.limited_parse(nds_id, batch, semaphore)
                        for batch in batches
                    ))
                    all_zip_infos = [info for batch in results for info in batch]

                # 计算下次扫描时间
                wait_time = max(self.min_interval, 
                              self.scan_interval - status.scan_duration)
                status.next_scan_time = datetime.now().timestamp() + wait_time
                status.is_scanning = False

                await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"Scan error for NDS {nds_id}: {str(e)}")
                self.status[nds_id].is_scanning = False
                await asyncio.sleep(self.min_interval)

    async def limited_parse(self, nds_id: int, file_paths: List[str], semaphore: asyncio.Semaphore) -> List[Dict]:
        """限制并发的文件解析"""
        zip_infos = []
        async with semaphore:
            zip_infos = await self.parse_zip_info(nds_id, file_paths)
        return zip_infos

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
