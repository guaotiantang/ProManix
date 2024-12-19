import asyncio
from contextlib import asynccontextmanager
import logging
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from .NDSClient import NDSClient, NDSError

logger = logging.getLogger(__name__)

@dataclass
class PoolConfig:
    """连接池配置"""
    protocol: str
    host: str
    port: int
    user: str
    passwd: str
    pool_size: int = 5  # 每个服务器的连接数
    max_idle_time: int = 300  # 最大空闲时间(秒)
    retry_count: int = 3  # 重试次数

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
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None

    def add_server(self, server_id: str, config: PoolConfig) -> None:
        """添加服务器配置"""
        self._configs[server_id] = config
        self._pools[server_id] = []
        
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
            passwd=config.passwd
        )
        await client.connect()
        return client

    async def _get_connection(self, server_id: str) -> ConnectionInfo:
        """获取一个可用连接"""
        if server_id not in self._configs:
            raise NDSError(f"Server {server_id} not configured")

        async with self._lock:
            # 查找空闲连接
            for conn in self._pools[server_id]:
                if not conn.in_use:
                    # 检查连接是否有效
                    try:
                        if await conn.client.check_connect():
                            conn.in_use = True
                            conn.last_used = datetime.now()
                            return conn
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

            # 等待有连接释放
            while True:
                for conn in self._pools[server_id]:
                    if not conn.in_use:
                        conn.in_use = True
                        conn.last_used = datetime.now()
                        return conn
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
        async with self._lock:
            now = datetime.now()
            for server_id, connections in self._pools.items():
                max_idle = self._configs[server_id].max_idle_time
                idle_limit = now - timedelta(seconds=max_idle)
                
                to_remove = []
                for conn in connections:
                    if not conn.in_use and conn.last_used < idle_limit:
                        await self._close_connection(conn)
                        to_remove.append(conn)
                
                for conn in to_remove:
                    connections.remove(conn)

    @asynccontextmanager
    async def get_client(self, server_id: str):
        """获取客户端连接的上下文管理器
        
        使用示例:
            async with pool.get_client("server1") as client:
                await client.some_operation()
        """
        conn = await self._get_connection(server_id)
        try:
            yield conn.client
        finally:
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

        async with self._lock:
            for connections in self._pools.values():
                for conn in connections:
                    await self._close_connection(conn)
            self._pools.clear() 

    async def remove_server(self, server_id: str) -> bool:
        """移除服务器配置及其所有连接
        
        Args:
            server_id: 服务器ID
            
        Returns:
            bool: 是否成功移除
            
        Raises:
            NDSError: 移除过程中发生错误
        """
        if server_id not in self._configs:
            return False
            
        async with self._lock:
            try:
                # 关闭所有连接
                for conn in self._pools[server_id]:
                    await self._close_connection(conn)
                
                # 移除配置和连接池
                del self._pools[server_id]
                del self._configs[server_id]
                
                return True
            except Exception as e:
                logger.error(f"Error removing server {server_id}: {e}")
                raise NDSError(f"Failed to remove server {server_id}: {str(e)}")

    def get_server_config(self, server_id: str) -> Optional[PoolConfig]:
        """获取服务器配置
        
        Args:
            server_id: 服务器ID
            
        Returns:
            Optional[PoolConfig]: 服务器配置，不存在时返回None
        """
        return self._configs.get(server_id)

    def get_server_ids(self) -> List[str]:
        """获取所有服务器ID列表
        
        Returns:
            List[str]: 服务器ID列表
        """
        return list(self._configs.keys())

    def get_pool_status(self, server_id: str) -> Dict[str, Any]:
        """获取连接池状态
        
        Args:
            server_id: 服务器ID
            
        Returns:
            Dict[str, Any]: 包含以下信息：
                - total_connections: 当前连接总数
                - active_connections: 正在使用的连接数
                - idle_connections: 空闲连接数
                
        Raises:
            NDSError: 服务器ID不存在
        """
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
        """获取所有连接池状态
        
        Returns:
            Dict[str, Dict[str, Any]]: server_id -> 状态信息的映射
        """
        return {
            server_id: self.get_pool_status(server_id)
            for server_id in self._configs
        }