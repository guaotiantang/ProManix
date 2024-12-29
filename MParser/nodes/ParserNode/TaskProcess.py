import json
import uuid
import signal
import asyncio
import websockets
from typing import List
from HttpClient import HttpClient
from multiprocessing import Manager
from aiomultiprocess import Process

from config import BACKEND_URL, NDS_GATEWAY_URL

class TaskProcess:
    def __init__(self, process_count: int = 2):
        self.process_count = process_count
        self.queue = Manager().Queue()
        self.status = Manager().dict()
        self.status_lock = Manager().Lock()
        self.is_running = False
        self.processes: List[Process] = []
        self._shutdown_event = Manager().Event()

    async def set_process_count(self, new_count: int):
        """动态设置进程数量"""
        if new_count == self.process_count:
            return

        if new_count < self.process_count:
            # 减少进程数量
            for _ in range(self.process_count - new_count):
                self.queue.put(None)  # 发送停止信号

            # 等待进程完成当前任务后退出
            while True:
                active_count = 0
                with self.status_lock:
                    for pid in range(self.process_count):
                        if self.status.get(f'P{pid}_Active', False): active_count += 1
                if active_count <= new_count:
                    break
                await asyncio.sleep(1)

            # 更新进程列表
            old_processes = self.processes[new_count:]
            self.processes = self.processes[:new_count]
            for p in old_processes:
                await p.join()

        else:
            # 增加进程数量
            with self.status_lock:
                self.status['process_count'] = new_count

            for pid in range(self.process_count, new_count):
                process = Process(
                    target=sub_process,
                    args=(pid, self.queue, self.status, self.status_lock, self._shutdown_event)
                )
                process.start()
                self.processes.append(process)

        self.process_count = new_count

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._shutdown_event.clear()
        with self.status_lock:
            self.status['process_count'] = self.process_count
            for pid in range(self.process_count):
                self.status[f'P{pid}_Active'] = False

        self.processes = [
            Process(
                target=sub_process,
                args=(pid, self.queue, self.status, self.status_lock, self._shutdown_event)
            ) for pid in range(self.process_count)
        ]
        for process in self.processes:
            process.start()

    async def stop(self):
        """停止所有进程"""
        if not self.is_running:
            return

        self._shutdown_event.set()
        self.is_running = False

        # 向队列发送停止信号
        for _ in range(len(self.processes)):
            self.queue.put(None)

        # 等待所有任务完成
        while not self.queue.empty():
            await asyncio.sleep(1)

        # 等待所有进程完成
        for process in self.processes:
            await process.join()

        self.processes.clear()

    @property
    def idle_process_count(self) -> int:
        """获取空闲进程数量"""
        idle_count = 0
        with self.status_lock:
            for pid in range(self.process_count):
                if not self.status[f'P{pid}_Active']:
                    idle_count += 1
        return idle_count


# noinspection PyBroadException
async def sub_process(pid, queue, status, lock, shutdown_event):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    run = True
    backend_client = HttpClient(BACKEND_URL)
    while run:
        try:
            if shutdown_event.is_set():
                run = False
                break
            with lock:
                status[f'P{pid}_Active'] = False
            task = queue.get()
            if task is None:
                break
            with lock:
                status[f'P{pid}_Active'] = True
            await parse_task(task, backend_client)
        except Exception:
            continue


async def parse_task(task, backend_client: HttpClient):
    try:
        ws_url = f"ws://{NDS_GATEWAY_URL.replace('http://', '')}/nds/ws/read/{uuid.uuid4()}"
        async with websockets.connect(ws_url) as websocket:
            await websocket.send(json.dumps({
                "NDSID": task['NDSID'],
                "FilePath": task['FilePath'],
                "HeaderOffset": task.get('HeaderOffset', 0),
                "CompressSize": task.get('CompressSize')
            }))
            data = await websocket.recv()
            if isinstance(data, bytes):
                print(f"Handle file {task['FilePath']}.{task['SubFileName']}")
                await asyncio.sleep(3)
                # TODO: 处理数据
                # 更新任务状态为成功
                await backend_client.post(
                    "ndsfile/update-parsed", 
                    json={"files": [{"FileHash": task.get('FileHash'), "Parsed": 2}]}
                )
            else:
                error_data = json.loads(data)
                raise Exception(json.dumps(error_data))
    except Exception as e:
        print(e)



