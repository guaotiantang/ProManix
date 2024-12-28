from aiomultiprocess import Process
import asyncio
from typing import List, Dict, Any, Optional
import signal
import logging
from HttpClient import HttpClient
from config import BACKEND_URL, NDS_GATEWAY_URL
import websockets
import uuid
import json
from multiprocessing import Queue, Value, Lock
import ctypes

logger = logging.getLogger(__name__)

# 全局共享状态
task_queue = Queue()  # 任务队列
active_count = Value(ctypes.c_int, 0)  # 活动进程计数
status_lock = Lock()  # 进程间共享的锁

async def worker_process():
    """工作进程主函数"""
    # 忽略中断信号
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    
    # 创建HTTP客户端
    backend_client = HttpClient(BACKEND_URL)
    print("SubProcess Start")
    try:
        while True:
            try:
                # 从队列获取任务（阻塞等待）
                print("Wait Queue...")
                task_data = task_queue.get()
                print("Parse Queue...")
                # 增加活动计数
                with status_lock:
                    active_count.value += 1
                
                try:
                    # 处理任务
                    await process_task(task_data, backend_client)
                finally:
                    # 无论任务是否成功，都减少活动计数
                    with status_lock:
                        active_count.value -= 1
                
            except Exception as e:
                logger.error(f"Error in worker process: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Worker process error: {e}")
    finally:
        await backend_client.close()

async def process_task(task_data: Dict[str, Any], backend_client: HttpClient):
    """处理单个任务的协程"""
    try:
        # 获取文件内容
        ws_url = f"ws://{NDS_GATEWAY_URL.replace('http://', '')}/nds/ws/read/{uuid.uuid4()}"
        async with websockets.connect(ws_url) as websocket:
            # 发送读取文件请求
            await websocket.send(json.dumps({
                "NDSID": task_data['NDSID'],
                "FilePath": task_data['FilePath'],
                "HeaderOffset": task_data.get('HeaderOffset', 0),
                "CompressSize": task_data.get('CompressSize')
            }))
            
            # 接收响应
            data = await websocket.recv()
            
            if isinstance(data, bytes):
                # TODO: 处理文件内容...
                print(f"Handle file {task_data['FilePath']}.{task_data['SubFileName']}")
                await asyncio.sleep(3)
                
                # 更新任务状态为成功
                await backend_client.post(
                    "ndsfile/update-parsed", 
                    json={"files": [{"FileHash": task_data["FileHash"], "Parsed": 2}]}
                )
            else:
                error_data = json.loads(data)
                raise Exception(json.dumps(error_data))
                
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
        
        # 启动工作进程
        i = 0
        for _ in range(self.process_count):
            i += 1
            print(f"Run Process[{i}]/{self.process_count}")
            process = Process(target=worker_process)  # worker_process 是协程函数
            process.start()
            self.processes.append(process)

        logger.info(f"Started {self.process_count} worker processes")

    async def stop(self):
        """停止所有工作进程"""
        if not self._running:
            return

        self._running = False
        
        # 停止所有进程
        for process in self.processes:
            process.terminate()
            await process.join()

        self.processes.clear()
        
        # 重置计数器
        with status_lock:
            active_count.value = 0
            
        logger.info("All worker processes stopped")

    def get_available_processes(self) -> int:
        """获取空闲进程数量"""
        with status_lock:
            return self.process_count - active_count.value

    def get_process_status(self) -> Dict[str, Any]:
        """获取详细的进程状态"""
        with status_lock:
            return {
                "total_processes": self.process_count,
                "active_processes": active_count.value,
                "available_processes": self.process_count - active_count.value
            }

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
