import asyncio
import aiohttp
import aiomysql
from DBEngine import MysqlPool
from Configure import ModuleInfo
from Utils import KeyType, Status
from fastapi import APIRouter, Body


class AsyncNDSDBService:
    def __init__(self):
        self.lock = KeyType()
        self.MysqlPool = MysqlPool()
        self.scanner_status = Status()
        self.parser_status = Status()

    async def init(self):
        if self.MysqlPool.pool is None:
            print("INFO NDS database pool staring...")
            await self.MysqlPool.init_pool(min_size=10, max_size=64)
            self.lock.log = asyncio.Lock()
            self.lock.nds_info = asyncio.Lock()
            self.lock.nds_file = asyncio.Lock()
            self.lock.zip_file = asyncio.Lock()
            print("INFO NDS database pool inited.")

    async def log(self, log_text, from_module, level=0):
        async with self.lock.log:
            conn = await self.MysqlPool.acquire()
            try:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "INSERT INTO Log (LogFrom, LogText, LogType) VALUES (%s, %s, %s)",
                        (from_module, str(log_text), level)
                    )
                    await conn.commit()
            except Exception as e:
                print(str(e))
            finally:
                await self.MysqlPool.release(conn)

    async def log_clean(self):
        async with self.lock.log:
            conn = await self.MysqlPool.acquire()
            try:
                async with conn.cursor() as cursor:
                    # noinspection SqlWithoutWhere
                    await cursor.execute("DELETE FROM Log ")
                    await conn.commit()
            except Exception as e:
                print(str(e))
            finally:
                await self.MysqlPool.release(conn)

    async def nds_info_get(self, nds_id=None):
        conn = await self.MysqlPool.acquire()
        try:
            async with conn.cursor() as cursor:
                if nds_id:
                    await cursor.execute("SELECT * FROM NDSList WHERE ID=%s", (nds_id,))
                    result = await cursor.fetchone()
                else:
                    await cursor.execute("SELECT * FROM NDSList")
                    result = await cursor.fetchall()
                return result
        except Exception as e:
            await self.log(
                from_module=f"AsyncNDSDBService.nds_info_get({nds_id})",
                level=1,
                log_text=str(e)
            )
            return None
        finally:
            await self.MysqlPool.release(conn)

    async def nds_file_sync(self, nds_id, file_list):

        async with self.lock.nds_file:
            conn = await self.MysqlPool.acquire()
            try:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT ID, NDSID, DataType, FilePath FROM NDSFileList WHERE NDSID = %s",
                                         (nds_id,))
                    db_results = await cursor.fetchall()
                    db_files = {row["FilePath"]: row["ID"] for row in db_results}
                    file_set = set(item["FilePath"] for item in file_list)

                    to_delete = [db_files[path] for path in db_files.keys() - file_set]
                    to_add = [item for item in file_list if item["FilePath"] not in db_files]

                    for i in range(0, len(to_delete), 100):
                        batch = to_delete[i:i + 100]
                        delete_query = "DELETE FROM NDSFileList WHERE ID IN (%s)" % ",".join(map(str, batch))
                        await cursor.execute(delete_query)

                    add_query = ("INSERT INTO NDSFileList (NDSID, DataType, FilePath, FileTime) "
                                 "VALUES (%s, %s, %s, %s) ON DUPLICATE KEY UPDATE AddTime=AddTime")
                    for i in range(0, len(to_add), 100):
                        batch = to_add[i:i + 100]
                        await cursor.executemany(
                            add_query,
                            [(nds_id, item["DataType"], item["FilePath"], item["FileTime"]) for item in batch]
                        )
                    await conn.commit()
                    return {
                        "nds_id": nds_id,
                        "delete": len(to_delete),
                        "add": len(to_add),
                    }
            except aiomysql.OperationalError as e:
                if e.args[0] == 1213:  # 死锁
                    return {
                        "nds_id": nds_id,
                        "delete": 0,
                        "add": 0,
                    }

            except Exception as e:
                await self.log(
                    from_module=f"AsyncNDSDBService.nds_file_sync({nds_id})",
                    level=1,
                    log_text=str(e)
                )
                return {
                    "nds_id": nds_id,
                    "delete": 0,
                    "add": 0,
                }
            finally:
                await self.MysqlPool.release(conn)

    async def nds_file_get(self, nds_id=None, limit=10):
        conn = await self.MysqlPool.acquire()
        try:
            async with conn.cursor() as cursor:
                if nds_id:
                    await cursor.execute(
                        "SELECT * FROM NDSFileList WHERE NDSID = %s AND Parsed = %s ORDER BY FileTime LIMIT %s",
                        (nds_id, 0, limit)
                    )
                else:
                    await cursor.execute(
                        "SELECT * FROM NDSFileList WHERE Parsed = %s ORDER BY FileTime",
                        (nds_id, 0)
                    )
                result = await cursor.fetchall()
                return result
        except Exception as e:
            await self.log(
                from_module=f"AsyncNDSDBService.nds_file_get({nds_id})",
                level=1,
                log_text=str(e)
            )
            return []
        finally:
            await self.MysqlPool.release(conn)

    async def get_nds_files_queue(self, nds_id, count=5):
        async with self.lock.zip_file:
            for attempt in range(3):
                conn = await self.MysqlPool.acquire()
                try:
                    async with conn.cursor() as cursor:
                        await cursor.callproc("GetNDSUNParseFiles", [nds_id, count])
                        result = await cursor.fetchall()
                        return result
                except aiomysql.OperationalError as e:
                    if e.args[0] == 1213:  # 死锁
                        if attempt == 2:  # 最大重试
                            return []
                except Exception as e:
                    await self.log(
                        from_module=f"AsyncNDSDBService.GetNDSUNParseFiles({nds_id})",
                        level=1,
                        log_text=str(e)
                    )
                    return []
                finally:
                    await self.MysqlPool.release(conn)

    async def nds_file_update(self, file_id, parsed=1):
        async with self.lock.nds_file:
            conn = await self.MysqlPool.acquire()
            try:
                async with conn.cursor() as cursor:
                    query = f"UPDATE NDSFileList SET Parsed = %s WHERE ID = %s"
                    await cursor.execute(query, (parsed, file_id))
                    await conn.commit()
            except Exception as e:
                await self.log(
                    from_module=f"AsyncNDSDBService.nds_file_update({file_id})",
                    level=1,
                    log_text=str(e)
                )
            finally:
                await self.MysqlPool.release(conn)

    async def zip_info_append(self, file_info, zip_sub_info):
        async with self.lock.nds_file:
            conn = await self.MysqlPool.acquire()
            try:
                async with conn.cursor() as cursor:
                    query = ("INSERT IGNORE INTO MZIPFileInfo ("
                             f"FileID, NDSID, eNodeBID, DataType, FileTime, FilePath, SubFileName, "
                             f"HeaderOffset, CompressSize, FileSize, FlaggBits, CompressType"
                             f") VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
                    values = [(
                        file_info.get("ID"), file_info.get("NDSID"), info.get("enodebid"), file_info.get("DataType"),
                        file_info.get("FileTime"), file_info.get("FilePath"), info.get("sub_file_name"),
                        info.get("header_offset"), info.get("compress_size"), info.get("file_size"),
                        info.get("flag_bits"),
                        info.get("compress_type")
                    ) for info in zip_sub_info]
                    await cursor.executemany(query, values)
                    query = f"UPDATE NDSFileList SET Parsed = %s, LockTime = NULL, TaskUUID = NULL WHERE ID = %s"
                    await cursor.execute(query, (1, file_info.get("ID")))
                    await conn.commit()
                    return True
            except Exception as e:
                await self.log(
                    from_module=f"AsyncNDSDBService.zip_info_append",
                    level=1,
                    log_text=str(e)
                )
                return False
            finally:
                await self.MysqlPool.release(conn)


nds_service_api = AsyncNDSDBService()


# noinspection HttpUrlsUsage
class NDSDatabaseWebAPI:
    def __init__(self):
        self.host = "127.0.0.1"  # ModuleInfo.get("ModuleParams").get("host")
        self.port = ModuleInfo.get("ModuleParams").get("port")
        self.base_url = f"http://{self.host}:{self.port}"
        self.connector = aiohttp.TCPConnector(limit=200)
        self.timeout = aiohttp.ClientTimeout(total=300, connect=60, sock_read=180, sock_connect=60)
        self.session = aiohttp.ClientSession(connector=self.connector, timeout=self.timeout)

    async def init_check(self, service_name):
        try:
            async with self.session.request("GET", self.base_url) as response:
                response.raise_for_status()
        except Exception:
            pass
        print(f"INFO {service_name} web session inited.")

    async def close(self):
        """关闭共享的 ClientSession"""
        try:
            await self.session.close()
        except Exception:
            pass

    async def _request(self, method, endpoint, params=None, json=None):
        """通用请求方法"""
        url = f"{self.base_url}{endpoint}"
        # 过滤掉 params 中的 None 值
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        try:
            async with self.session.request(method, url, params=params, json=json) as response:
                response.raise_for_status()  # 检查 HTTP 错误状态码
                data = await response.json()
                return data.get("result", None)
        except aiohttp.ClientError as e:
            print(f"ERROR aiohttp error:{e} -URL: {url}")
            return None

    async def log(self, log_text, from_module, level=0):
        """记录日志"""
        return await self._request(
            method="POST",
            endpoint="/log/put",
            json={"message": log_text, "from": from_module, "level": level}
        )

    async def nds_info_get(self, nds_id=None):
        """获取 NDS 信息"""
        return await self._request(
            method="GET",
            endpoint="/nds/get",
            params={"nds_id": nds_id}
        )

    async def nds_file_get(self, nds_id=None, limit=10):
        """获取 NDS 文件信息"""
        return await self._request(
            method="GET",
            endpoint="/nfs/get",
            params={"nds_id": nds_id, "limit": limit}
        )

    async def nds_file_queue_get(self, nds_id=None, limit=5):
        """获取 NDS 文件信息"""
        return await self._request(
            method="GET",
            endpoint="/nfs/queue",
            params={"nds_id": nds_id, "limit": limit}
        )

    async def nds_file_sync(self, nds_id, file_list):
        """同步 NDS 文件列表"""
        return await self._request(
            method="POST",
            endpoint="/nfs/sync",
            json={"nds_id": nds_id, "file_list": file_list}
        )

    async def nds_file_update(self, file_id, parsed=1):
        """更新 NDS 文件状态"""
        return await self._request(
            method="POST",
            endpoint="/nfs/update",
            json={"file_id": file_id, "parsed": parsed}
        )

    async def zip_info_append(self, file_info, zip_sub_info):
        """追加 ZIP 文件信息"""
        return await self._request(
            method="POST",
            endpoint="/parse/append",
            json={"file_info": file_info, "zip_sub_info": zip_sub_info}
        )

    async def nds_scanner_status_set(self, data):
        return await self._request(
            method="POST",
            endpoint="/nfs/status/set",
            json=data
        )

    async def nds_parser_status_set(self, data):
        return await self._request(
            method="POST",
            endpoint="/parse/status/set",
            json=data
        )


log_router = APIRouter(prefix="/log")
nds_info_route = APIRouter(prefix="/nds")
nds_file_route = APIRouter(prefix="/nfs")
nds_parser_router = APIRouter(prefix="/parse")


@log_router.post("/put")
async def log_put(log: dict = Body(...)):
    await nds_service_api.log(
        log_text=log.get("message", ""),
        from_module=log.get("from", ""),
        level=log.get("level", 0)
    )
    return {"result": "done"}


@log_router.get("/clean")
async def log_clean():
    await nds_service_api.log_clean()
    return {"result": "done"}


@nds_info_route.get("/get")
async def nds_info_get(nds_id: int = None):
    return {"result": await nds_service_api.nds_info_get(nds_id)}


@nds_file_route.get("/get")
async def nds_file_get(nds_id: int, limit: int = 10):
    return {"result": await nds_service_api.nds_file_get(nds_id, limit)}


@nds_file_route.get("/queue")
async def nds_files_get_queue(nds_id: int, limit: int = 5):
    return {"result": await nds_service_api.get_nds_files_queue(nds_id, limit)}


@nds_file_route.post("/sync")
async def nds_file_sync(data: dict = Body(...)):
    nds_id = data.get("nds_id")
    file_list = data.get("file_list")
    return {"result": await nds_service_api.nds_file_sync(nds_id, file_list)}


@nds_file_route.post("/update")
async def nds_file_update(data: dict = Body(...)):
    file_id = data.get("file_id")
    parsed = data.get("parsed", 1)
    return {"result": await nds_service_api.nds_file_update(file_id, parsed)}


@nds_parser_router.post("/append")
async def zip_info_append(data: dict = Body(...)):
    file_info = data.get("file_info")
    zip_sub_info = data.get("zip_sub_info")
    return {"result": await nds_service_api.zip_info_append(file_info, zip_sub_info)}


@nds_file_route.get("/status/get")
async def scanner_status():
    return await nds_service_api.scanner_status.get_status()


@nds_file_route.post("/status/set")
async def scanner_status_set(data: dict = Body(...)):
    await nds_service_api.scanner_status.set_status(data)
    return {"result": "done"}


@nds_parser_router.get("/status/get")
async def scanner_status():
    return await nds_service_api.parser_status.get_status()


@nds_parser_router.post("/status/set")
async def scanner_status_set(data: dict = Body(...)):
    await nds_service_api.parser_status.set_status(data)
    return {"result": "done"}
