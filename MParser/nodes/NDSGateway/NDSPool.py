import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional
from dataclasses import dataclass
from NDSClient import NDSClient

logger = logging.getLogger(__name__)


class NDSError(Exception):
    """NDS错误"""
    pass


@dataclass
class PoolConfig:
    """连接池配置"""
    protocol: str
    host: str
    port: int
    user: str
    passwd: str
    pool_size: int = 2


@dataclass
class ConnectionInfo:
    """连接信息"""
    client: Optional[NDSClient]


class NDSPool:
    """NDS连接池管理器"""

    def __init__(self):
        self._pools: Dict[str, asyncio.Queue[ConnectionInfo]] = {}  # server_id -> connection queue
        self._configs: Dict[str, PoolConfig] = {}  # server_id -> config
        self.nds_log = {}

    def add_server(self, server_id: str, config: PoolConfig) -> None:
        """添加服务器配置"""
        self._configs[server_id] = config
        self._pools[server_id] = asyncio.Queue(maxsize=config.pool_size)
        self.nds_log[server_id] = 0

    @asynccontextmanager
    async def get_client(self, server_id: str):
        """获取客户端连接的上下文管理器"""
        if server_id not in self._configs:
            raise NDSError(f"Server {server_id} not configured")

        queue = self._pools[server_id]
        conn = None

        try:
            # 1. 尝试从队列获取连接
            try:
                conn = queue.get_nowait()
                if not conn.client or not await conn.client.check_connect():
                    await self._close_connection(conn)
                    conn = None
            except asyncio.QueueEmpty:
                pass

            # 2. 如果没有可用连接，创建新连接
            if not conn:
                if queue.qsize() < self._configs[server_id].pool_size:
                    config = self._configs[server_id]
                    client = NDSClient(
                        protocol=config.protocol,
                        host=config.host,
                        port=config.port,
                        user=config.user,
                        passwd=config.passwd,
                        nds_id=server_id
                    )
                    await client.connect()
                    conn = ConnectionInfo(client=client)
                else:
                    # 3. 如果队列已满，等待可用连接
                    conn = await queue.get()  # 无限等待直到有可用连接
                    if not conn.client or not await conn.client.check_connect():
                        await self._close_connection(conn)
                        raise NDSError("Failed to get valid connection")

            yield conn.client

        except Exception as e:
            if conn:
                await self._close_connection(conn)
            logger.error(f"Error in get_client: {e}")
            raise NDSError(f"Failed to get client: {e}")

        finally:
            if conn and conn.client:  # 只有当连接有效时才放回队列
                try:
                    await queue.put(conn)
                except Exception as e:
                    logger.error(f"Error releasing connection: {e}")
                    await self._close_connection(conn)

    @staticmethod
    async def _close_connection(conn: ConnectionInfo) -> None:
        """关闭连接"""
        if conn and conn.client:
            try:
                await conn.client.close_connect()
            except Exception as e:
                logger.error(f"Error closing connection: {e}")
            finally:
                conn.client = None

    async def close(self) -> None:
        """关闭连接池"""
        for server_id, queue in self._pools.items():
            while not queue.empty():
                try:
                    conn = queue.get_nowait()
                    await self._close_connection(conn)
                except asyncio.QueueEmpty:
                    break
                except Exception as e:
                    logger.error(f"Error closing connection: {e}")

        self._pools.clear()
        self._configs.clear()
        logger.info("Connection pool closed")

    async def remove_server(self, server_id: str) -> None:
        """移除服务器配置"""
        if server_id not in self._configs:
            return

        # 关闭所有连接
        queue = self._pools[server_id]
        while not queue.empty():
            try:
                conn = queue.get_nowait()
                await self._close_connection(conn)
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Error closing connection: {e}")

        # 移除配置
        del self._pools[server_id]
        del self._configs[server_id]
        del self.nds_log[server_id]
        logger.info(f"Server {server_id} removed from pool")

    def get_pool_status(self, server_id: str) -> Dict:
        """获取指定服务器的连接池状态"""
        if server_id not in self._configs:
            raise NDSError(f"Server {server_id} not configured")

        queue = self._pools[server_id]
        config = self._configs[server_id]
        return {
            "server_id": server_id,
            "protocol": config.protocol,
            "host": config.host,
            "port": config.port,
            "max_connections": config.pool_size,
            "available": config.pool_size - queue.qsize(),
            "current_connections": queue.qsize()
        }

    def get_all_pool_status(self) -> Dict:
        """获取所有连接池的状态"""
        return {
            server_id: self.get_pool_status(server_id)
            for server_id in self._configs
        }

    def get_server_ids(self) -> list:
        """获取所有已配置的服务器ID列表"""
        return list(self._configs.keys())
