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

import pandas as pd
from lxml import etree


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


# noinspection HttpUrlsUsage,PyBroadException
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
                                if task_data.get("DataType", "").upper() == "MRO" and file_name.lower().endswith(".xml"):
                                    await parse_mro_data(task_data, content)
                                elif task_data.get("DataType", "").upper() == "MDT" and file_name.lower().endswith(".csv"):
                                    await parse_mdt_data(task_data, content)
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


async def parse_mro_data(task_data, content):
    """解析 MRO 数据"""
    try:
        result = []
        
        # 定义需要检查的字段
        smr_check = [
            "MR_LteScEarfcn", "MR_LteScPci", "MR_LteScRSRP",
            "MR_LteNcEarfcn", "MR_LteNcPci", "MR_LteNcRSRP"
        ]
        
        
        tree = etree.fromstring(content)
        LteScENBID = tree.find('.//eNB').attrib['id'] # 提取eNodeBID
        
        for measurement in tree.findall('.//measurement'):
            smr_content = measurement.find('smr').text.strip()
            smr_content = smr_content.replace('MR.', 'MR_')
            smr_fields = smr_content.split()
            data = []

            if not set(smr_check).issubset(set(smr_fields)):
                continue # 检查必要字段是否存在，当不存在时跳过该measurement节点
                
            headers = ["MR_LteScENBID"] + smr_check  # 字段列表(添加MR_LteScENBID)
            smr_values = {x: i for i, x in enumerate(smr_fields) if x in smr_check}  # 字段索引映射
            max_field_num = smr_values[max(smr_values, key=smr_values.get)]  # 找出所需字段中最后的索引位置
            for obj in measurement.findall('object'):  # 遍历每个measurement下的object元素
                for v in obj.findall('v'):  # 遍历每个object下的v元素（<v></v>）
                    values = v.text.strip().split()  # 分割v元素内的文本内容
                    if len(values) >= max_field_num: # 如果值的数量不够，跳过这条记录
                        # 构建一行数据：[LteScENBID] + [对应位置的测量值]
                        row_data = [LteScENBID] + [values[smr_values[x]] for x in headers[1:]]
                        if 'NIL' not in row_data:
                            data.append(row_data)  # 如果数据中没有NIL（无效值），则添加到数据列表中

            df = pd.DataFrame(data, columns=headers)  # 将数据转换为DataFrame
        
            # 数据类型转换和计算
            df[[
                'MR_LteScPci', 'MR_LteScRSRP',
                'MR_LteNcPci', 'MR_LteNcRSRP'
            ]] = df[[
                'MR_LteScPci', 'MR_LteScRSRP',
                'MR_LteNcPci', 'MR_LteNcRSRP'
            ]].astype(int)  # 将PCI和RSRP字段转换为整数类型
        
            # 计算同频6db和MOD3采样点数
            df['MR_LteFCIn6db'] = ((df['MR_LteScEarfcn'] == df['MR_LteNcEarfcn']) &
                                   (df['MR_LteScRSRP'] - df['MR_LteNcRSRP'] <= 6)).astype(int)

            # 计算MOD3采样点数
            df['MR_LTEMod3'] = ((df['MR_LteScEarfcn'] == df['MR_LteNcEarfcn']) &
                               (df['MR_LteScPci'] % 3 == df['MR_LteNcPci'] % 3) &
                               (df['MR_LteScRSRP'] - df['MR_LteNcRSRP'] <= 3) &
                               (df['MR_LteScRSRP'] >= 30)).astype(int)

            # 数值转换 - 将字符串转换为数值，如果无法转换则设置为NaN
            for col in smr_check:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 数据分组统计 - 按指定字段分组，统计每组的和以及平均值
            grouped = df.groupby(
                ["MR_LteScENBID", "MR_LteScEarfcn", "MR_LteScPci", "MR_LteNcEarfcn", "MR_LteNcPci"]
            ).agg(
                MR_LteScSPCount=pd.NamedAgg(column="MR_LteScRSRP", aggfunc='count'),
                MR_LteScRSRPAvg=pd.NamedAgg(column="MR_LteScRSRP", aggfunc=lambda x: x.mean()),
                MR_LteNcSPCount=pd.NamedAgg(column="MR_LteNcRSRP", aggfunc='count'),
                MR_LteNcRSRPAvg=pd.NamedAgg(column="MR_LteNcRSRP", aggfunc=lambda x: x.mean()),
                MR_LteCC6Count=pd.NamedAgg(column="MR_LteFCIn6db", aggfunc='sum'),
                MR_LteMOD3Count=pd.NamedAgg(column="MR_LTEMod3", aggfunc='sum')
            ).reset_index()
        
            # 添加DataTime时间字段(15分钟粒度文件时间)
            grouped['DataTime'] = pd.to_datetime(task_data.get('FileTime'))
        
            # 类型转换，确保与数据库类型一致
            grouped['MR_LteScENBID'] = grouped['MR_LteScENBID'].astype('int8')
            grouped['MR_LteScEarfcn'] = grouped['MR_LteScEarfcn'].astype('int32')
            grouped['MR_LteScPci'] = grouped['MR_LteScPci'].astype('int8')
            grouped['MR_LteNcEarfcn'] = grouped['MR_LteNcEarfcn'].astype('int32')
            grouped['MR_LteNcPci'] = grouped['MR_LteNcPci'].astype('int32')

            result.append(grouped.to_dict('records'))  # 将处理后的数据添加到结果中
        return result
        
    except Exception as e:
        print("MRO Parse Error:", str(e))
        raise Exception(f"MRO Parse Error: {str(e)}")


async def parse_mdt_data(task, data):
    print(task, "parse mdt data length: ", len(data))
    # TODO: 解析数据
