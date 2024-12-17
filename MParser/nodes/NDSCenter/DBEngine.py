import aiomysql
from Configure import *
from aiomysql.cursors import DictCursor


class MysqlPool:
    def __init__(self):
        self.pool = None

    async def init_pool(self, min_size=10, max_size=200, autocommit=False):
        self.pool = await aiomysql.create_pool(
            host=MysqlInfo.get("host"),
            port=MysqlInfo.get("port"),
            user=MysqlInfo.get("user"),
            password=MysqlInfo.get("passwd"),
            db=MysqlInfo.get("db_name"),
            autocommit=autocommit,
            minsize=min_size,
            maxsize=max_size,
            cursorclass=DictCursor,
            echo=False
        )

    async def acquire(self):
        if self.pool is None:
            await self.init_pool()
            if self.pool is None:
                raise RuntimeError("连接池尚未初始化")
        return await self.pool.acquire()

    async def release(self, conn):
        if self.pool is None:
            await self.init_pool()
            if self.pool is None:
                raise RuntimeError("连接池尚未初始化")
        await self.pool.release(conn)

    async def close_pool(self):
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            self.pool = None
