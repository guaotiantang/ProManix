import asyncio
from contextlib import asynccontextmanager
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from NDSClient import NDSClient, NDSError

logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """连接池配置"""
    protocol: str
    host: str
    port: int
    user: str
    passwd: str
    pool_size: int = 2  # 每个服务器的连接数
    max_idle_time: int = 300  # 最大空闲时间(秒)
    retry_count: int = 3  # 重试次数
    wait_timeout: int = 3600  # 等待连接的超时时间(秒)，默认1小时


@dataclass
class ConnectionInfo:
    """连接信息"""
    client: NDSClient
    in_use: bool = False
    last_used: datetime = datetime.now()


class NDSPool:
    """NDS连接池管理器"""

    def __init__(self):
        self._pools: Dict[str, List[ConnectionInfo]] = {}  # server_id -> connections
        self._configs: Dict[str, PoolConfig] = {}  # server_id -> config
        self._locks: Dict[str, asyncio.Lock] = {}  # server_id -> lock
        self._global_lock = asyncio.Lock()  # 用于修改字典结构的全局锁
        self._cleanup_task: Optional[asyncio.Task] = None

        self.nds_log = {}

    async def _get_server_lock(self, server_id: str) -> asyncio.Lock:
        """获取服务器专用的锁"""
        async with self._global_lock:
            if server_id not in self._locks:
                self._locks[server_id] = asyncio.Lock()
            return self._locks[server_id]

    def add_server(self, server_id: str, config: PoolConfig) -> None:
        """添加服务器配置"""
        self._configs[server_id] = config
        self._pools[server_id] = []
        self.nds_log[server_id] = 0
        if server_id not in self._locks:
            self._locks[server_id] = asyncio.Lock()

        if not self._cleanup_task:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _create_client(self, server_id: str) -> NDSClient:
        """创建新的客户端连接"""
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
        return client

    async def _get_connection(self, server_id: str) -> ConnectionInfo:
        """获取一个可用连接"""
        if server_id not in self._configs:
            print(f"Server {server_id} not configured")
            raise NDSError(f"Server {server_id} not configured")

        lock = await self._get_server_lock(server_id)
        async with lock:
            while True:  # 持续等待直到有可用连接
                # 查找空闲连接
                for conn in self._pools[server_id]:
                    if not conn.in_use:
                        try:
                            if await conn.client.check_connect():
                                conn.in_use = True
                                conn.last_used = datetime.now()
                                return conn
                            else:
                                logger.warning(f"NDS[{server_id}] Connection check failed")
                                await self._close_connection(conn)
                                self._pools[server_id].remove(conn)
                        except Exception as e:
                            logger.warning(f"Connection check failed: {e}")
                            await self._close_connection(conn)
                            self._pools[server_id].remove(conn)

                # 如果没有可用连接且未达到池上限，创建新连接
                config = self._configs[server_id]
                if len(self._pools[server_id]) < config.pool_size:
                    client = await self._create_client(server_id)
                    conn = ConnectionInfo(client=client, in_use=True)
                    self._pools[server_id].append(conn)
                    return conn

                # 等待一段时间后重试
                await asyncio.sleep(0.1)

    async def _close_connection(self, conn: ConnectionInfo) -> None:
        """关闭连接"""
        try:
            await conn.client.close_connect()
        except Exception as e:
            logger.error(f"Error closing connection: {e}")

    async def _cleanup_loop(self) -> None:
        """定期清理空闲连接"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self._cleanup_idle_connections()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    async def _cleanup_idle_connections(self) -> None:
        """清理空闲连接"""
        # 先获取所有需要处理的服务器ID
        async with self._global_lock:
            server_ids = list(self._pools.keys())

        # 逐个处理每个服务器的连接
        for server_id in server_ids:
            try:
                lock = await self._get_server_lock(server_id)
                async with lock:
                    if server_id not in self._pools:  # 再次检查，因为可能已被删除
                        continue

                    connections = self._pools[server_id]
                    max_idle = self._configs[server_id].max_idle_time
                    idle_limit = datetime.now() - timedelta(seconds=max_idle)

                    to_remove = []
                    for conn in connections:
                        if not conn.in_use and conn.last_used < idle_limit:
                            await self._close_connection(conn)
                            to_remove.append(conn)

                    for conn in to_remove:
                        connections.remove(conn)
            except Exception as e:
                logger.error(f"Error cleaning up connections for server {server_id}: {e}")

    @asynccontextmanager
    async def get_client(self, server_id: str):
        """获取客户端连接的上下文管理器"""
        conn = await self._get_connection(server_id)
        try:
            yield conn.client
        finally:
            lock = await self._get_server_lock(server_id)
            async with lock:
                conn.in_use = False
                conn.last_used = datetime.now()

    async def close(self) -> None:
        """关闭连接池"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        async with self._global_lock:
            for server_id in list(self._pools.keys()):
                await self.remove_server(server_id)

    async def remove_server(self, server_id: str) -> bool:
        """移除服务器配置及其所有连接"""
        if server_id not in self._configs:
            return False

        # 先获取全局锁
        async with self._global_lock:
            # 获取服务器锁（如果存在）
            server_lock = self._locks.get(server_id)
            if server_lock:
                async with server_lock:
                    try:
                        # 关闭所有连接
                        for conn in self._pools[server_id]:
                            await self._close_connection(conn)

                        # 移除配置和连接池
                        self._pools.pop(server_id, None)
                        self._configs.pop(server_id, None)
                        self._locks.pop(server_id, None)

                        return True
                    except Exception as e:
                        logger.error(f"Error removing server {server_id}: {e}")
                        raise NDSError(f"Failed to remove server {server_id}: {str(e)}")

    def get_server_config(self, server_id: str) -> Optional[PoolConfig]:
        """获取服务器配置"""
        return self._configs.get(server_id)

    def get_server_ids(self) -> List[str]:
        """获取所有服务器ID列表"""
        return list(self._configs.keys())

    def get_pool_status(self, server_id: str) -> Dict[str, Any]:
        """获取连接池状态"""
        if server_id not in self._configs:
            raise NDSError(f"Server {server_id} not configured")

        connections = self._pools[server_id]
        active = sum(1 for conn in connections if conn.in_use)

        return {
            "total_connections": len(connections),
            "active_connections": active,
            "idle_connections": len(connections) - active,
            "max_connections": self._configs[server_id].pool_size
        }

    def get_all_pool_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有连接池状态"""
        return {
            server_id: self.get_pool_status(server_id)
            for server_id in self._configs
        }
