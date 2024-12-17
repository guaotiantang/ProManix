
import re
import asyncio
from time import time
from Utils import AsyncDict
from NDSClient import NDSClient
from multiprocessing import Event
from aiomultiprocess import Process
from ErrorException import ScanError
from NDSDBApi import NDSDatabaseWebAPI
from datetime import datetime, timedelta


class NDSFileScanService:
    def __init__(self):
        self.stop_event = Event()
        self.api: NDSDatabaseWebAPI = None
        self.process = None
        self.__router = None
        self.nds_queue: AsyncDict = None

    async def run(self):
        print("INFO NDSFileScanService process loading... ")
        if not self.process or not self.process.is_alive():
            self.stop_event.clear()
            self.process = Process(target=self._run_service, args=(self.stop_event,))
            self.process.start()
            print("INFO NDSFileScanService process starting... ")

    async def stop(self):
        if self.process and self.process.is_alive():
            self.stop_event.set()  # 触发停止事件
            await asyncio.sleep(1)  # 等待子进程完成
            await self.process.join()  # 等待子进程结束
        else:
            print("Process is not running.")

    async def _run_service(self, stop_event):
        print("INFO Service[NDSFileScanService] delay 15s...")
        wait_time = 15
        while wait_time > 0:
            st = 5 if wait_time >= 5 else wait_time
            wait_time -= st
            await asyncio.sleep(st)
            if stop_event.is_set():
                return
        self.api = NDSDatabaseWebAPI()
        await self.api.init_check("NDSFileScanService")
        await self._async_run_service(stop_event)

    async def _async_run_service(self, stop_event):
        await self.api.log("Start", "NDSFileScanService.Start", 0)
        self.nds_queue = AsyncDict()
        print("INFO Service[NDSFileScanner] started.")
        tasks = []
        while not stop_event.is_set():
            start_time = time()
            nds = await self.api.nds_info_get()
            nds = nds if nds else []
            for info in nds:
                if info and info["Switch"] == 1 and info["ID"] not in self.nds_queue.dict:
                    tasks.append(asyncio.create_task(self.scan_nds_files(info, stop_event)))
            end_time = time()
            elapsed_time = end_time - start_time
            wait_time = max(0, int(30 - elapsed_time))

            while wait_time > 0:
                st = 5 if wait_time >= 5 else wait_time
                wait_time -= st
                await asyncio.sleep(st)
                if stop_event.is_set():
                    break
            status = {
                "ID": "ScannerInfo",
                "Tasks": self.nds_queue.dict,
                "TaskCount": len(tasks)
            }
            await self.api.nds_scanner_status_set(status)
        try:
            await self.api.close()
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    async def scan_nds_files(self, nds_info, stop_event):
        await self.nds_queue.put(nds_info["ID"], nds_info.get("NDSName"))
        status = {
            "ID": nds_info.get("ID"),
            "StartTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        client = NDSClient(
            protocol=nds_info.get("Protocol"),
            host=nds_info.get("Address"),
            port=nds_info.get("Port"),
            user=nds_info.get("Account"),
            passwd=nds_info.get("Password")
        )

        while not stop_event.is_set():
            start_time = datetime.now()
            try:
                status.update({"ScanTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                status.update({"Status": "Scanning"})
                await self.api.nds_scanner_status_set(status)
                nds = await self.api.nds_info_get(nds_info.get("ID"))
                if not isinstance(nds, dict) or nds.get("Switch", 0) != 1:
                    break
                # 重新获取NDS配置进行连接扫描
                client.protocol = nds.get("Protocol")
                client.host = nds.get("Address")
                client.port = nds.get("Port")
                client.user = nds.get("Account")
                client.passwd = nds.get("Password")
                if nds.items() != nds_info.items() or not await client.check_connect():
                    nds_info = nds
                    await client.connect()
                nds_file_list = []

                file_list = await client.scan(
                    scan_path=nds_info.get("MRO_Path"),
                    filter_pattern=nds_info.get("MRO_Filter")
                ) if nds_info.get("MRO_Path", None) is not None else []
                if file_list and len(file_list) > 0:
                    nds_file_list.extend(_structure_nds_file_info(file_list, "MRO"))
                file_list = await client.scan(
                    scan_path=nds_info.get("MDT_Path"),
                    filter_pattern=nds_info.get("MDT_Filter")
                ) if nds_info.get("MRO_Path", None) is not None else []
                if file_list and len(file_list) > 0:
                    nds_file_list.extend(_structure_nds_file_info(file_list, "MDT"))
                if len(nds_file_list) > 0:
                    res = await self.api.nds_file_sync(nds_info.get("ID"), nds_file_list)
                    status.update(res)
                status.pop("LastErrTime", None)
                status.pop("LastError", None)
            except ScanError as e:
                await self.api.log(e.message, e.from_module, e.level)
                err_status = {
                    "LastErrTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "LastError": str(e.message)
                }
                status.update(err_status)
            except Exception as e:
                await self.api.log(str(e), f"NDSFileScanService.scan_nds_files({nds_info.get('ID')})", 1)
                status.update({
                    "LastErrTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "LastError": str(e)
                })

            end_time = start_time + timedelta(seconds=300)
            while datetime.now() < end_time:
                remaining_time = (end_time - datetime.now()).total_seconds()
                sleep_time = min(5, remaining_time)
                status.update({"Status": f"Wait({int(remaining_time)}s)"})
                if sleep_time <= 0 or stop_event.is_set():
                    break
                await self.api.nds_scanner_status_set(status)
                await asyncio.sleep(sleep_time)

        status.update({"EndTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        await self.api.nds_scanner_status_set(status)
        await self.nds_queue.remove(nds_info["ID"])


def _structure_nds_file_info(files, data_type):
    file_map = []
    for file in files:
        try:
            match = re.search(r"_([0-9]{14})(?:[^/]*?)?\.zip$", file)  # 匹配MDT/MRO时间
            if match:
                dt = datetime.strptime(match.group(1), "%Y%m%d%H%M%S")
                dt = dt.strftime("%Y-%m-%d %H:%M:%S")
                file_info = {
                    "DataType": data_type,
                    "FilePath": file,
                    "FileTime": dt
                }
                file_map.append(file_info)
        except Exception:
            pass
    return file_map
