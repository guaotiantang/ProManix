from aiomultiprocess import Process, Pool
import asyncio
from typing import List, Dict, Any, Optional
import signal
import logging
from HttpClient import HttpClient
from config import BACKEND_URL, NDS_GATEWAY_URL
import websockets
import uuid
import json
from multiprocessing import Manager, Value, Lock
import ctypes

logger = logging.getLogger(__name__)

# 全局共享状态
active_count = Value(ctypes.c_int, 0)
status_lock = Lock()

class TaskProcessor:
    def __init__(self, process_count: int):
        self.process_count = process_count
        self.processes: List[Process] = []
        self._running = False
        

    async def start(self):
        """启动所有工作进程"""
        if self._running:
            return

        self._running = True
        
        # 创建进程池
        self.pool = Pool(processes=self.process_count)
        # 初始化Manager和共享队列
        self.manager = Manager()
        self.task_queue = self.manager.Queue()
        # 启动工作进程
        for i in range(self.process_count):
            process = Process(target=worker_task, args=(self.task_queue, i))
            process.start()
            self.processes.append(process)
            print(f"Started worker process {i}")
        
        print(f"Started {self.process_count} worker processes")

    async def stop(self):
        """停止所有工作进程"""
        if not self._running:
            return

        self._running = False
        
        # 发送结束信号
        for _ in range(self.process_count):
            self.task_queue.put(None)
            
        # 等待所有任务完成
        if self.pool:
            await self.pool.join()
            await self.pool.close()
        
        # 关闭Manager
        self.manager.shutdown()
        
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
                "available_processes": self.process_count - active_count.value,
                "queue_size": self.task_queue.qsize()
            }

    def put_task(self, task: Dict[str, Any]):
        """添加任务到队列"""
        self.task_queue.put(task)

async def worker_task(queue, worker_id):
    """工作进程任务"""
    # 忽略中断信号
    print(f"Worker {worker_id} process starting...")
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    
    # 创建HTTP客户端
    backend_client = HttpClient(BACKEND_URL)
    try:
        while True:
            try:
                # 从队列获取任务（阻塞等待）
                print(f"Worker {worker_id} waiting for task...")
                task_data = queue.get()
                if task_data is None:  # 接收到结束信号，退出
                    print(f"Worker {worker_id} exiting...")
                    break
                    
                print(f"Worker {worker_id} processing task...")
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
                logger.error(f"Error in worker {worker_id}: {e}")
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

