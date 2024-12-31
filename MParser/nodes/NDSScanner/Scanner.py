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
        self.scan_interval = 300  # 扫描间隔（秒）
        self.min_interval = 5  # 最小等待时间（秒）
        self.interval = 5  # 批次间等待时间（秒）

        # 状态管理
        self.status: Dict[int, ScanStatus] = {}  # NDS状态字典
        self._tasks: Dict[int, asyncio.Task] = {}  # 扫描任务字典
        self._running = False  # 运行状态标志
        self._lock = asyncio.Lock()  # 任务管理锁

        # 正则表达式
        self._time_pattern = re.compile(r'[_-](\d{14})')  # 时间提取模式
        self.task_check_interval = 30  # 任务检查间隔（秒）

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
            name: 文件名，任意包含 _YYYYMMDDHHMMSS 或 -YYYYMMDDHHMMSS 的格式：
        Returns:
            str: 格式化的时间字符串，如 '2024-12-20 02:30:00'
                 如果无法提取时间，返回None
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
        return None

    # ========== 核心扫描功能 ==========

    async def scan_nds(self, nds_config: Dict) -> List[Dict]:
        """扫描单个NDS的文件
        
        扫描指定NDS的MRO和MDT文件，返回文件列表。
        每个文件包含path和type信息。
        """
        try:
            # 扫描MRO文件
            mro_files = await self._scan_files(nds_config['ID'], nds_config['MRO_Path'], nds_config['MRO_Filter'],
                                               "MRO")
            # 扫描MDT文件
            mdt_files = await self._scan_files(nds_config['ID'], nds_config['MDT_Path'], nds_config['MDT_Filter'],
                                               "MDT")

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
        
        Args:
            nds_id: NDS ID
            files: 文件列表，每个文件包含 path 和 type 属性
            
        Returns:
            List[Dict]: 解析后的文件信息列表
        """
        try:
            json_data = {
                "nds_id": nds_id,
                "file_paths": [file['path'] for file in files]
            }
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
                    file_data = next((f for f in files if f['path'] == file_path), None)
                    if file_data:
                        zip_infos.extend(
                            self._create_file_records(
                                nds_id,
                                file_path,
                                {"DataType": file_data['type']},  # 只传递需要的数据
                                info['info']
                            )
                        )
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
            if file_time:
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
        """获取新增文件信息列表
        
        Args:
            nds_id: NDS ID
            files: 当前扫描到的文件列表，格式: [{"path": str, "type": str}, ...]
                
        Returns:
            List[Dict]: 需要新增的文件列表，保持输入格式
        """
        if not files:
            return []
        
        try:
            # 1. 扫描结果自身去重
            unique_files = {(f['path'], f.get('type', '')): f for f in files}
            files = list(unique_files.values())

            # 2. 获取数据库文件列表和任务时间映射
            result = await self.backend_client.get(f"ndsfile/files?nds_id={nds_id}")
            if not isinstance(result, dict) or 'data' not in result or not result['data']:
                return []

            # 3. 处理文件删除
            existing_files = set(result['data'].get('files', []))
            current_paths = {f['path'] for f in files}
            # 使用海象运算符(:=),计算数据库中有，NDS上没有的文件进行删除
            if files_to_delete := list(existing_files - current_paths):  
                try:
                    await self.backend_client.post(
                        "ndsfile/remove",
                        json={"nds_id": nds_id, "files": files_to_delete}
                    )
                except Exception as e:
                    logger.error(f"Failed to delete files: {e}")

            # 4. 任务时间范围过滤
            task_times = result['data'].get('times', [])
            print(task_times) 
            if not task_times:
                return []  # 没有任务, 无需继续
            # 5. 筛选新文件并匹配时间范围
            new_files = [f for f in files if f['path'] not in existing_files]  # 提取服务器中没有的文件清单
            res_files = []
            for new_file in new_files:
                new_file_time = datetime.strptime(self._extract_time_from_name(new_file['path']), '%Y-%m-%d %H:%M:%S')
                if not new_file_time:
                    continue
                for task_time in task_times:
                    start_time = datetime.strptime(task_time['StartTime'], '%Y-%m-%d %H:%M:%S')
                    end_time = datetime.strptime(task_time['EndTime'], '%Y-%m-%d %H:%M:%S')
                    if not start_time or not end_time:
                        continue
                    if new_file_time >= start_time and new_file_time <= end_time:
                        print(f"NewFile: {new_file} Time: {start_time} <= {new_file_time} <= {end_time} Map: {task_time}")
                        res_files.append(new_file)
                        break
                    
                    
            return res_files
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
                        "ndsfile/batch",
                        json={"files": group_infos}
                    )
                except Exception as e:
                    logger.error(f"Failed to submit file {file_path}: {str(e)}")
                    continue  # 继续下一轮

        except Exception as e:
            logger.error(f"Submit file infos error: {str(e)}")

    async def has_pending_tasks(self, nds_id: int) -> bool:
        """检查NDS是否有待处理的任务"""
        try:
            response = await self.backend_client.get(f"ndsfile/check-tasks/{nds_id}")
            if isinstance(response, dict) and 'data' in response:
                return response['data']
            return False
        except Exception as e:
            logger.error(f"Failed to check pending tasks: {e}")
            return False

    async def scan_loop(self, nds_config: Dict):
        """单个NDS的扫描循环"""
        nds_id = nds_config['ID']
        self.status[nds_id] = ScanStatus()

        while self._running:
            try:
                # 检查是否有待处理的任务
                while await self.has_pending_tasks(nds_id):
                    print(f"NDS {nds_id} has pending tasks, waiting {self.task_check_interval} seconds...")
                    await asyncio.sleep(self.task_check_interval)
                status = self.status[nds_id]
                status.is_scanning = True
                start_time = datetime.now()

                # 执行扫描
                files = await self.scan_nds(nds_config)
                if not files:
                    continue

                new_files = await self.diff_files(nds_id, files)

                # 更新状态
                status.last_scan_time = start_time
                status.scan_duration = (datetime.now() - start_time).total_seconds()
                status.new_files_count = len(new_files)

                # 如果有新文件，处理它们
                if new_files:
                    # 处理新文件, 每次扫描2个文件，避免长时间等待
                    batches = [new_files[i:i + 2] for i in range(0, len(new_files), 2)]
                    for batch in batches:
                        try:
                            zip_infos = await self.parse_zip_info(nds_id, batch)
                            if zip_infos:
                                # 最后提交文件信息
                                await self.submit_file_infos(zip_infos)
                        except Exception as e:
                            logger.error(f"Failed to process batch: {str(e)}")

                # 计算下次扫描时间
                self.interval = max(self.min_interval, self.scan_interval - status.scan_duration)

            except Exception as e:
                self.interval = self.min_interval
                logger.error(f"Scan error for NDS {nds_id}: {str(e)}")

            finally:
                # 更新下次扫描时间并确保延迟执行
                self.status[nds_id].next_scan_time = datetime.now().timestamp() + self.interval
                self.status[nds_id].is_scanning = False
                await asyncio.sleep(self.interval)  # 确保每轮扫描后都有延迟

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

                    # 启动新扫描任务
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

            # 获取初始配置
            configs = await self.fetch_nds_configs()
            if not configs:
                logger.warning("No NDS configs found")
                return

            # 检查网关状态
            try:
                gateway_status = await self.gateway_client.get("/")  # 调用网关的根路径检查接口
                if not isinstance(gateway_status, dict) or gateway_status.get('code') != 200:
                    logger.error("Gateway is not ready")
                    return

                # 检查每个NDS的连接状态
                valid_configs = []
                for config in configs:
                    try:
                        check_result = await self.gateway_client.post(
                            "check",
                            json={
                                "Protocol": config['Protocol'],
                                "Address": config['Address'],
                                "Port": config['Port'],
                                "Account": config['Account'],
                                "Password": config['Password']
                            }
                        )

                        if isinstance(check_result, dict) and check_result.get('code') == 200:
                            valid_configs.append(config)
                        else:
                            logger.warning(
                                f"NDS {config['ID']} connection check failed: "
                                f"{check_result.get('message', 'Unknown error')}"
                            )

                    except Exception as e:
                        logger.error(f"Failed to check NDS {config['ID']}: {str(e)}")
                        continue

                if not valid_configs:
                    logger.warning("No valid NDS connections found")
                    return

                # 只启动通过连接检查的NDS扫描任务
                self._running = True
                print("Scanner Started")
                for config in valid_configs:
                    self._tasks[config['ID']] = asyncio.create_task(self.scan_loop(config))

            except Exception as e:
                logger.error(f"Failed to check gateway status: {str(e)}")

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

        def format_status(_status: ScanStatus) -> Dict:
            """格式化单个状态对象"""
            return {
                "last_scan_time": _status.last_scan_time.strftime(
                    '%Y-%m-%d %H:%M:%S') if _status.last_scan_time else None,
                "next_scan_time": datetime.fromtimestamp(_status.next_scan_time).strftime(
                    '%Y-%m-%d %H:%M:%S') if _status.next_scan_time else None,
                "new_files_count": _status.new_files_count,
                "scan_duration": _status.scan_duration,
                "is_scanning": _status.is_scanning,
                "last_scan_file": _status.last_scan_file,
                "scan_file_info": _status.scan_file_info
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
