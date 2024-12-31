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
from clickhouse_driver import Client as CKClient

from HttpClient import HttpClient
from Parser import mro, mdt
from config import BACKEND_URL, NDS_GATEWAY_URL, CK_HOST, CK_PORT, CK_USER, CK_PASSWD, CK_DB


class TaskProcess:
    def __init__(self, process_count: int = 2):
        self.process_count = process_count
        self.queue = Manager().Queue()
        self.status = Manager().dict()
        self.status_lock = Manager().Lock()
        self.is_running = False
        self.processes: List[Process] = []
        self._shutdown_event = Manager().Event()
        self.ck_config = {}

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
        print("MultiProcess Starting...")
        self.ck_config["host"] = CK_HOST
        self.ck_config["port"] = CK_PORT
        self.ck_config["user"] = CK_USER
        self.ck_config["passwd"] = CK_PASSWD
        self.ck_config["db"] = CK_DB
        self.is_running = True
        self._shutdown_event.clear()
        with self.status_lock:
            self.status['process_count'] = self.process_count
            for pid in range(self.process_count):
                self.status[f'P{pid}_Active'] = False

        self.processes = [
            Process(
                target=sub_process,
                args=(pid, self.queue, self.status, self.status_lock, self._shutdown_event, self.ck_config)
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
async def sub_process(pid, queue, status, lock, shutdown_event, ck_config):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    run = True
    backend_client = HttpClient(BACKEND_URL)
    print(f"SubProcess[{pid}] Started.")
    try:
        clickhouse = CKClient(
            host=ck_config["host"],
            port=ck_config["port"],
            user=ck_config["user"],
            password=ck_config["passwd"],
            database=ck_config["db"]
        )
        clickhouse.execute('SELECT 1')
    except Exception as e:
        print(f"Init ClickHouse Error: {str(e)}")
        return
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
            await parse_task(task, backend_client, clickhouse)
        except Exception:
            with lock:
                status[f'P{pid}_Active'] = False
            continue


async def update_status(backend_client: HttpClient, file_hash: str, value: int):
    """更新任务状态"""
    try:
        await backend_client.post(
            "ndsfile/update-parsed",
            json={"files": [{"FileHash": file_hash, "Parsed": value}]}
        )
    except Exception:
        pass


# noinspection HttpUrlsUsage,PyBroadException,SqlDialectInspection
async def parse_task(task_data: Dict[str, Any], backend_client: HttpClient, clickhouse: CKClient):
    """处理单个任务的协程"""
    try:
        # 数据库配置
        ck_set = {
            'max_insert_threads': 2,
            'insert_distributed_sync': 0,
            'async_insert': 1,
            'wait_for_async_insert': 0
        }

        # 任务类型配置
        task_type = task_data.get("DataType", "").upper()
        config = {
            "MRO": (".xml", "LTE_MRO", mro),
            "MDT": (".csv", "LTE_MDT", mdt)
        }.get(task_type)

        if not config:
            raise ValueError("Invalid task type")

        file_suffix, table_name, parser_func = config

        # 获取并处理文件
        ws_url = f"ws://{NDS_GATEWAY_URL.replace('http://', '')}/nds/ws/read/{uuid.uuid4()}"
        async with websockets.connect(ws_url, max_size=2 ** 30) as websocket:
            await websocket.send(json.dumps({
                "NDSID": task_data['NDSID'],
                "FilePath": task_data['FilePath'],
                "HeaderOffset": task_data.get('HeaderOffset', 0),
                "CompressSize": task_data.get('CompressSize')
            }))

            file_data = bytearray()
            while True:
                data = await websocket.recv()
                if isinstance(data, str):
                    json_data = json.loads(data)
                    if json_data.get("end_of_file"):
                        break
                    if "code" in json_data:
                        raise Exception(json.dumps(json_data))
                else:
                    file_data.extend(data)
        if not file_data:
            raise ValueError("Empty file data")

        with zipfile.ZipFile(io.BytesIO(file_data)) as zip_file:
            data_files = [f for f in zip_file.namelist() if f.lower().endswith(file_suffix)]
            for data_file in data_files:
                with zip_file.open(data_file) as f:
                    data = f.read()
                    try:
                        for res in parser_func(data):
                            if res:
                                sql = f"INSERT INTO {table_name} ({', '.join(res[0].keys())}) VALUES"
                                clickhouse.execute(sql, res, settings=ck_set)
                        await update_status(backend_client, task_data["FileHash"], 2)  # 成功
                    except Exception as e:
                        print("Err:", e)
                        await update_status(backend_client, task_data["FileHash"], -2)  # 解析失败

    except zipfile.BadZipFile:
        await update_status(backend_client, task_data["FileHash"], -2)  # ZIP文件错误
    except Exception as e:
        print("Error:", e)
        # 处理文件不存在等错误
        try:
            error_data = json.loads(str(e)) if isinstance(str(e), str) else e
            status = -1 if error_data.get("code") == 404 else -2
        except Exception:
            status = -2
        await update_status(backend_client, task_data["FileHash"], status)
