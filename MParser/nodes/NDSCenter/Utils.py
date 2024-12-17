import re
import asyncio


class KeyType(dict):
    def __getattr__(self, item):
        if item not in self:
            return None
        return self[item]

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, item):
        if item in self:
            del self[item]


def is_regex(pattern):
    # 检查正则表达式合法性
    try:
        re.compile(pattern)
        return True
    except re.error:
        return False


class Status:
    def __init__(self):
        self.status = {}
        self.__lock = asyncio.Lock()

    async def get_status(self):
        return self.status

    async def set_status(self, data):
        async with self.__lock:
            status = {key: value for key, value in data.items() if key != "ID"}
            self.status[data.get("ID")] = status


class AsyncDict:
    def __init__(self):
        self.dict = {}
        self.__lock = asyncio.Lock()

    async def put(self, key, value):
        async with self.__lock:
            self.dict[key] = value

    async def remove(self, key):
        async with self.__lock:
            self.dict.pop(key, None)

    async def get(self, key):
        return self.dict.get(key, None)
