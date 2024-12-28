from aiomultiprocess import Queue, Process, AioManager
import asyncio
from typing import List, Dict, Any, Optional
import signal
import logging
from HttpClient import HttpClient
from config import BACKEND_URL, NDS_GATEWAY_URL
import websockets
import uuid
import json

logger = logging.getLogger(__name__)

# 全局任务队列和共享计数器
task_queue = Queue()
manager = AioManager()
idle_count = manager.Value('i', 0)  # 共享的空闲进程计数器

class TaskProcessor:
    def __init__(self, process_count: int):
        self.process_count = process_count
        self.processes: List[Process] = []
        self._running = False
        self._lock = asyncio.Lock()
        self.ws_connections: Dict[str, websockets.WebSocketClientProtocol] = {}

    async def start(self):
        """启动所有工作进程"""
        if self._running:
            return

        self._running = True
        
        # 启动指定数量的工作进程
        for _ in range(self.process_count):
            process = Process(target=self._worker_entry)
            process.daemon = True
            process.start()
            self.processes.append(process)
            # 初始时所有进程都是空闲的
            with idle_count.get_lock():
                idle_count.value += 1

        logger.info(f"Started {self.process_count} worker processes")

    async def stop(self):
        """停止所有工作进程"""
        if not self._running:
            return

        self._running = False
        
        # 等待所有进程完成当前任务并退出
        for process in self.processes:
            process.terminate()
            process.join()

        self.processes.clear()
        # 重置空闲计数
        with idle_count.get_lock():
            idle_count.value = 0
        logger.info("All worker processes stopped")

    def get_available_processes(self) -> int:
        """获取空闲进程数量"""
        return idle_count.value

    async def get_file_content(self, nds_id: int, file_path: str, header_offset: int = 0, compress_size: Optional[int] = None) -> bytes:
        """通过WebSocket获取文件内容"""
        # 生成唯一的客户端ID
        client_id = str(uuid.uuid4())
        
        # WebSocket URL
        ws_url = f"ws://{NDS_GATEWAY_URL.replace('http://', '')}/nds/ws/read/{client_id}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                # 发送读取文件请求
                await websocket.send(json.dumps({
                    "NDSID": nds_id,
                    "FilePath": file_path,
                    "HeaderOffset": header_offset,
                    "CompressSize": compress_size
                }))
                
                # 接收单个响应后返回
                data = await websocket.recv()
                
                # 如果是二进制数据
                if isinstance(data, bytes):
                    return data
                
                # 如果是错误消息
                error_data = json.loads(data)
                raise Exception(json.dumps(error_data))  # 保持错误信息格式
                    
        except Exception as e:
            logger.error(f"Failed to get file content: {e}")
            raise

    @staticmethod
    def _worker_entry():
        """工作进程入口函数"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        
        try:
            loop.run_until_complete(TaskProcessor._process_loop())
        except Exception as e:
            logger.error(f"Worker process error: {e}")
        finally:
            loop.close()

    @staticmethod
    async def _process_loop():
        """工作进程主循环"""
        backend_client = HttpClient(BACKEND_URL)
        while True:
            try:
                # 标记为空闲状态
                with idle_count.get_lock():
                    idle_count.value += 1
                
                # 从队列获取任务（阻塞等待）
                task_data = await task_queue.get()
                
                # 获取到任务，标记为忙碌状态
                with idle_count.get_lock():
                    idle_count.value -= 1
                
                # 处理任务
                await TaskProcessor._process_task(task_data, backend_client)
                
            except Exception as e:
                logger.error(f"Error processing task: {e}")
                continue

    @staticmethod
    async def _process_task(task_data: Dict[str, Any], backend_client: HttpClient):
        """处理单个任务的协程"""
        try:
            # 获取文件内容
            data = await processor.get_file_content(
                nds_id=task_data['NDSID'],
                file_path=task_data['FilePath'],
                header_offset=task_data.get('HeaderOffset', 0),
                compress_size=task_data.get('CompressSize')
            )
            
            # TODO: 处理文件内容...
            print(f"Handle file {task_data['FilePath']}.{task_data['SubFileName']}")
            await asyncio.sleep(3)
            
            # 更新任务状态为成功
            await backend_client.post(
                "ndsfile/update-parsed", 
                json={"files": [{"FileHash": task_data["FileHash"], "Parsed": 2}]}
            )
            
        except Exception as e:
            parsed_status = -2
            try:
                error_data = json.loads(str(e))
                # 根据错误码判断
                parsed_status = -1 if error_data.get("code") == 404 else -2
            except Exception:
                pass
            await backend_client.post(
                "ndsfile/update-parsed", 
                json={"files": [{"FileHash": task_data["FileHash"], "Parsed": parsed_status}]}
            )
            

# 创建任务处理器实例
processor: TaskProcessor = None

async def init_processor(process_count: int):
    """初始化任务处理器"""
    global processor
    processor = TaskProcessor(process_count)
    await processor.start()

async def shutdown_processor():
    """关闭任务处理器"""
    if processor:
        await processor.stop()
