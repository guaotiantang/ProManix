import asyncio
from time import time
from Utils import AsyncDict
from NDSClient import NDSClient
from multiprocessing import Event
from aiomultiprocess import Process
from ErrorException import ScanError
from NDSDBApi import NDSDatabaseWebAPI
from datetime import datetime, timedelta


class ZIPParserService:
    def __init__(self):
        self.nds_semaphores = {}
        self.stop_event = Event()
        self.api: NDSDatabaseWebAPI = None
        self.process = None
        self.__router = None
        self.nds_queue: AsyncDict = None

    async def run(self):
        print("INFO ZIPParserService process loading... ")
        if not self.process or not self.process.is_alive():
            self.stop_event.clear()
            self.process = Process(target=self._run_service, args=(self.stop_event,))
            self.process.start()
            print("INFO ZIPParserService process starting... ")

    async def stop(self):
        if self.process and self.process.is_alive():
            self.stop_event.set()  # 触发停止事件
            await asyncio.sleep(1)  # 等待子进程完成
            await self.process.join()  # 等待子进程结束
        else:
            print("Process is not running.")

    async def _run_service(self, stop_event):
        print("INFO Service[ZIPParserService] delay 60s...")
        wait_time = 60
        while wait_time > 0:
            st = 5 if wait_time >= 5 else wait_time
            wait_time -= st
            await asyncio.sleep(st)
            if stop_event.is_set():
                return
        self.api = NDSDatabaseWebAPI()
        await self.api.init_check("ZIPParserService")
        await self._async_run_service(stop_event)

    async def _async_run_service(self, stop_event):
        await self.api.log("Start", "ZIPParserService.Start")
        self.nds_queue = AsyncDict()
        print("INFO Service[ZIPParserService] started.")
        tasks = []
        while not stop_event.is_set():
            start_time = time()
            nds = await self.api.nds_info_get()
            nds = nds if nds else []
            for info in nds:
                if info["Switch"] == 1 and info["ID"] not in self.nds_queue.dict:
                    # 初始化信号量，按 Address 限制最大协程数为 3
                    address = info["Address"]
                    if address not in self.nds_semaphores:
                        self.nds_semaphores[address] = asyncio.Semaphore(3)
                    tasks.append(asyncio.create_task(self.parse_zip_files(info, stop_event)))
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
                "ID": "ParserInfo",
                "Tasks": self.nds_queue.dict,
                "TaskCount": len(tasks)
            }
            await self.api.nds_parser_status_set(status)
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

    async def parse_zip_files(self, nds_info, stop_event):
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
        address = nds_info["Address"]  # 获取当前 Address
        semaphore = self.nds_semaphores[address]  # 按 Address 获取信号量

        while not stop_event.is_set():
            start_time = datetime.now()
            nds_files = []
            try:
                # 从 API 获取 NDS 信息
                nds = await self.api.nds_info_get(nds_info.get("ID"))
                if not isinstance(nds, dict) or nds.get("Switch", 0) != 1:
                    break
                if nds.items() != nds_info.items():
                    nds_info = nds

                # 更新 Client 配置
                client.protocol = nds.get("Protocol")
                client.host = nds.get("Address")
                client.port = nds.get("Port")
                client.user = nds.get("Account")
                client.passwd = nds.get("Password")
                # 更新状态
                status.update({
                    "ParseTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Status": "Waiting Semaphore",
                })
                await self.api.nds_parser_status_set(status)

                # 使用信号量限制每个 Address 的并发任务数
                async with semaphore:
                    # 从 API 获取文件队列
                    nds_files = await self.api.nds_file_queue_get(nds_info.get("ID"), 8)
                    # 更新状态
                    status.update({
                        "ParseTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Status": "Parsing",
                        "Files": len(nds_files)
                    })
                    await self.api.nds_parser_status_set(status)
                    for file in nds_files:
                        try:
                            if not await client.check_connect():
                                await client.connect()
                            if await client.file_exists(file.get("FilePath")):
                                await client.open(file.get("FilePath"))
                                info = await client.get_zip_info()
                                if info and len(info) > 0:
                                    await self.api.zip_info_append(file, info)
                            else:
                                await self.api.nds_file_update(file.get("ID"), -1)
                        except ScanError as e:
                            await self.api.nds_file_update(file.get("ID"), -1)
                            await self.api.log(e.message, e.from_module, e.level)
                        except Exception as e:
                            await self.api.nds_file_update(file.get("ID"), -1)
                            await self.api.log(
                                log_text=f"ParseFile[{file.get('FilePath')}] Error: {str(e)}",
                                from_module=f"ZIPParserService.parse_zip_files({nds_info.get('ID')})",
                                level=1
                            )

            except ScanError as e:
                await self.api.log(e.message, e.from_module, e.level)
                err_status = {
                    "LastErrTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "LastError": str(e.message)
                }
                status.update(err_status)
            except Exception as e:
                await self.api.log(str(e), f"ZIPParserService.parse_zip_files({nds_info.get('ID')})", 1)
                status.update({
                    "LastErrTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "LastError": str(e)
                })

            if not nds_files or len(nds_files) == 0:
                end_time = start_time + timedelta(seconds=60)
                while datetime.now() < end_time:
                    remaining_time = (end_time - datetime.now()).total_seconds()
                    sleep_time = min(5, remaining_time)
                    status.update({"Status": f"Wait({int(remaining_time)}s)"})
                    if sleep_time <= 0 or stop_event.is_set():
                        break
                    await self.api.nds_parser_status_set(status)
                    await asyncio.sleep(sleep_time)
            else:
                await asyncio.sleep(3)
        status.update({"EndTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        await self.api.nds_parser_status_set(status)
