import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from HttpClient import HttpClient
import re
from itertools import chain

logger = logging.getLogger(__name__)

@dataclass
class ScanStatus:
    """扫描状态数据类
    
    Attributes:
        last_scan_time: 上次扫描时间
        next_scan_time: 下次扫描时间
        new_files_count: 新文件数量
        scan_duration: 扫描持续时间
        is_scanning: 是否正在扫描
        last_scan_file: 上次扫描的文件路径
        scan_file_info: 上次扫描文件的详细信息，包含 NDSID、FilePath、FileTime 等字段
    """
    last_scan_time: Optional[datetime] = None
    next_scan_time: Optional[datetime] = None
    new_files_count: int = 0
    scan_duration: float = 0.0
    is_scanning: bool = False
    last_scan_file: Optional[str] = None
    scan_file_info: Optional[Dict[str, Any]] = None

class NDSScanner:
    """NDS文件扫描器
    
    负责扫描NDS服务器上的文件，解析文件信息并提交到后端数据库。
    支持NDS实例并发扫描，每个实例独立运行。
    """

    def __init__(self):
        # HTTP客户端
        self.backend_client = None  # 后端服务客户端
        self.gateway_client = None  # 网关服务客户端
        
        # 扫描配置
        self.scan_interval = 300    # 扫描间隔（秒）
        self.min_interval = 5       # 最小等待时间（秒）
        self.interval = 5          # 批次间等待时间（秒）
        
        # 状态管理
        self.status: Dict[int, ScanStatus] = {}  # NDS状态字典
        self._tasks: Dict[int, asyncio.Task] = {}  # 扫描任务字典
        self._running = False  # 运行状态标志
        self._lock = asyncio.Lock()  # 任务管理锁
        
        # 正则表达式
        self._time_pattern = re.compile(r'[_-](\d{14})')  # 时间提取模式

    # ========== 初始化和清理 ==========

    async def init_scanner(self, backend_url: str, gateway_url: str):
        """初始化扫描器，创建HTTP客户端"""
        self.backend_client = HttpClient(backend_url)
        self.gateway_client = HttpClient(gateway_url)

    async def close(self):
        """关闭扫描器，释放资源"""
        if self.backend_client:
            await self.backend_client.close()
        if self.gateway_client:
            await self.gateway_client.close()

    # ========== 辅助功能 ==========

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
    

    # ========== 核心扫描功能 ==========

    async def scan_nds(self, nds_config: Dict) -> List[Dict]:
        """扫描单个NDS的文件
        
        扫描指定NDS的MRO和MDT文件，返回文件列表。
        每个文件包含path和type信息。
        """
        try:
            print(f"扫描NDS[{nds_config['ID']}]")
            # 扫描MRO文件
            mro_files = await self._scan_files(nds_config['ID'], nds_config['MRO_Path'], nds_config['MRO_Filter'], "MRO")
            # 扫描MDT文件
            mdt_files = await self._scan_files(nds_config['ID'], nds_config['MDT_Path'], nds_config['MDT_Filter'], "MDT")
            
            print(f"NDS FilesCount[{len(list(chain(mro_files, mdt_files)))}]")
            return list(chain(mro_files, mdt_files))

        except Exception as e:
            logger.error(f"Scan error: {str(e)}")
            return []

    async def _scan_files(self, nds_id: int, path: str, pattern: str, data_type: str) -> List[Dict]:
        """扫描指定类型的文件"""
        response = await self.gateway_client.post(
            "nds/scan",
            json={
                "nds_id": nds_id,
                "scan_path": path,
                "filter_pattern": pattern,
                "data_type": data_type
            }
        )
        return [{"path": f, "type": data_type} for f in (response if isinstance(response, list) else [])]

    async def parse_zip_info(self, nds_id: int, files: List[Dict]) -> List[Dict]:
        """解析ZIP文件信息
        
        解析ZIP文件的详细信息，包括子文件列表、大小、时间等。
        返回符合NDSFileList格式的数据列表。
        """
        try:
            json_data = {"nds_id": nds_id, "file_paths": [file['FilePath'] for file in files]}
            print(f"NDS[{nds_id}]parse_zip_info")
            result = await self.gateway_client.post("nds/zip-info", json=json_data)
            return self._process_zip_info(nds_id, files, result)
        except Exception as e:
            logger.error(f"Parse ZIP info error: {str(e)}")
            return []

    def _process_zip_info(self, nds_id: int, files: List[Dict], result: Dict) -> List[Dict]:
        """处理ZIP信息响应数据"""
        zip_infos = []
        if isinstance(result, dict) and 'data' in result:
            for file_path, info in result['data'].items():
                if info['status'] == 'success':
                    file_data = next((f for f in files if f['FilePath'] == file_path), None)
                    if file_data:
                        zip_infos.extend(self._create_file_records(nds_id, file_path, file_data, info['info']))
        return zip_infos

    def _create_file_records(self, nds_id: int, file_path: str, file_data: Dict, info_list: List[Dict]) -> List[Dict]:
        """创建文件记录"""
        records = []
        for file_info in info_list:
            file_time = (
                self._extract_time_from_name(file_info['sub_file_name']) 
                if file_info.get('sub_file_name') 
                else self._extract_time_from_name(file_path)
            )
            
            records.append({
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
                'Parsed': 0
            })
        return records

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

    async def diff_files(self, nds_id: int, files: List[Dict]) -> List[Dict]:
        """获取新增文件信息列表"""
        try:
            
            result = await self.backend_client.get(f"nds/files?nds_id={str(nds_id)}")
            
            return result['new_files'] if isinstance(result, dict) and 'new_files' in result else []
        except Exception as e:
            logger.error(f"Diff files error: {str(e)}")
            return []

    async def submit_file_infos(self, file_infos: List[Dict]) -> None:
        """提交文件信息到后端"""
        try:
            # 按FilePath分组
            file_groups = {}
            for info in file_infos:
                file_path = info['FilePath']
                if file_path not in file_groups:
                    file_groups[file_path] = []
                file_groups[file_path].append(info)

            for file_path, group_infos in file_groups.items():
                try:
                    
                    await self.backend_client.post(
                        "nds/files/batch",
                        json={"files": group_infos}
                    )
                    logger.info(f"Successfully submitted file: {file_path} ({len(group_infos)} records)")
                except Exception as e:
                    logger.error(f"Failed to submit file {file_path}: {str(e)}")
                    continue  # 继续下一轮

        except Exception as e:
            logger.error(f"Submit file infos error: {str(e)}")

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
                if not files:  # 如果扫描失败，等待后重试
                    await asyncio.sleep(self.min_interval)
                    continue

                new_files = await self.diff_files(nds_id, files)
                if new_files is None:  # 如果比对失败，等待后重试
                    await asyncio.sleep(self.min_interval)
                    continue

                # 更新状态
                status.last_scan_time = start_time
                status.scan_duration = (datetime.now() - start_time).total_seconds()
                status.new_files_count = len(new_files)
                
                # 处理新文件, 每次最多处理前10个文件，避免协程等待时间过长
                handle_files = new_files
                if handle_files:
                    # 处理新文件, 每次扫描2个文件，避免长时间等待
                    batches = [handle_files[i:i + 2] for i in range(0, len(handle_files), 2)]
                    for batch in batches:
                        try:
                            await asyncio.sleep(0.5)  # 批次间短暂延迟
                            zip_infos = await self.parse_zip_info(nds_id, batch)
                            if zip_infos:
                                # 先记录状态，再提交文件信息
                                last_file = batch[-1]
                                status.last_scan_file = last_file.get('path')
                                
                                # 找到对应的 zip_info 记录
                                matching_zip_infos = [info for info in zip_infos if info['FilePath'] == status.last_scan_file]
                                if matching_zip_infos:
                                    status.scan_file_info = matching_zip_infos[-1]
                                
                                # 最后提交文件信息
                                await self.submit_file_infos(zip_infos)
                                
                            
                        except Exception as e:
                            logger.error(f"Failed to process batch: {str(e)}")
                            # 清除可能不完整的状态记录
                            status.last_scan_file = None
                            status.scan_file_info = None

                # 计算下次扫描时间
                self.interval = max(self.min_interval, self.scan_interval - status.scan_duration)
            except Exception as e:
                self.interval = self.min_interval
                logger.error(f"Scan error for NDS {nds_id}: {str(e)}")
            finally:
                self.status[nds_id].next_scan_time = datetime.now().timestamp() + self.interval
                self.status[nds_id].is_scanning = False
                await asyncio.sleep(self.interval)


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

    def get_status(self, nds_id: Optional[int] = None) -> Union[Dict[int, Dict], Optional[Dict]]:
        """获取扫描状态
        
        Args:
            nds_id: NDS ID，如果为None则返回所有NDS的状态
            
        Returns:
            如果指定nds_id: 返回单个NDS的状态字典或None（如果不存在）
            如果nds_id为None: 返回所有NDS的状态字典
        """
        def format_status(status: ScanStatus) -> Dict:
            """格式化单个状态对象"""
            return {
                "last_scan_time": status.last_scan_time.strftime('%Y-%m-%d %H:%M:%S') if status.last_scan_time else None,
                "next_scan_time": datetime.fromtimestamp(status.next_scan_time).strftime('%Y-%m-%d %H:%M:%S') if status.next_scan_time else None,
                "new_files_count": status.new_files_count,
                "scan_duration": status.scan_duration,
                "is_scanning": status.is_scanning,
                "last_scan_file": status.last_scan_file,
                "scan_file_info": status.scan_file_info
            }
        
        if nds_id is not None:
            status = self.status.get(nds_id)
            return format_status(status) if status else None
        
        return {
            nds_id: format_status(status)
            for nds_id, status in self.status.items()
        }

# 创建全局实例
scanner = NDSScanner() 
