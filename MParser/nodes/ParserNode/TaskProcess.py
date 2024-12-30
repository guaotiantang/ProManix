import asyncio
import io
import json
import signal
import uuid
import zipfile
from multiprocessing import Manager
from typing import List, Dict, Any

import websockets
from aiomultiprocess import Process

from HttpClient import HttpClient
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
                        if self.status.get(f'P{pid}_Active', False):
                            active_count += 1
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
    print(f"SubProcess[{pid}] Satrted.")
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
            with lock:
                status[f'P{pid}_Active'] = False
            continue


async def parse_task(task_data: Dict[str, Any], backend_client: HttpClient):
    """处理单个任务的协程"""
    try:
        # 获取文件内容
        ws_url = f"ws://{NDS_GATEWAY_URL.replace('http://', '')}/nds/ws/read/{uuid.uuid4()}"
        async with websockets.connect(ws_url, max_size=None) as websocket:  # 移除大小限制
            # 发送读取文件请求
            await websocket.send(json.dumps({
                "NDSID": task_data['NDSID'],
                "FilePath": task_data['FilePath'],
                "HeaderOffset": task_data.get('HeaderOffset', 0),
                "CompressSize": task_data.get('CompressSize')
            }))

            # 接收响应
            file_data = bytearray()
            while True:
                data = await websocket.recv()
                if isinstance(data, str):
                    # 处理JSON消息
                    json_data = json.loads(data)
                    if json_data.get("end_of_file"):
                        break
                    elif "code" in json_data:  # 检查是否为错误响应
                        raise Exception(json.dumps(json_data))
                else:
                    file_data.extend(data)

            if file_data:
                try:
                    # 使用BytesIO读取zip文件内容
                    with zipfile.ZipFile(io.BytesIO(file_data)) as zip_file:
                        # 读取每个文件的内容
                        for file_name in zip_file.namelist():
                            with zip_file.open(file_name) as f:
                                content = f.read()
                                if task_data.get("DataType", None) == "MRO" and file_name.endswith(".xml"):
                                    await parse_mro_data(content)
                                elif task_data.get("DataType", None) == "MDT" and file_name.endswith(".csv"):
                                    await parse_mdt_data(content)
                                else:
                                    raise Exception("No parser type")

                        # 更新任务状态为成功
                        await backend_client.post(
                            "ndsfile/update-parsed",
                            json={"files": [{"FileHash": task_data["FileHash"], "Parsed": 2}]}
                        )
                except zipfile.BadZipFile:
                    # ZIP文件无法读取，更新任务状态为失败
                    await backend_client.post(
                        "ndsfile/update-parsed",
                        json={"files": [{"FileHash": task_data["FileHash"], "Parsed": -2}]}
                    )

    except Exception as e:
        parsed_status = -2
        try:
            error_data = json.loads(str(e)) if isinstance(str(e), str) else e
            # 根据错误码判断
            parsed_status = -1 if error_data.get("code") == 404 else -2
        except Exception:
            pass
        await backend_client.post(
            "ndsfile/update-parsed",
            json={"files": [{"FileHash": task_data["FileHash"], "Parsed": parsed_status}]}
        )


async def parse_mro_data(data):
    print("parse mro data length: ", len(data))
    # TODO: 解析数据


async def parse_mdt_data(data):
    print("parse mdt data length: ", len(data))
    # TODO: 解析数据
