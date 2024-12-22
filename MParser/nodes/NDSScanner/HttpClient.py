import aiohttp
import logging
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)

@dataclass
class HttpConfig:
    """HTTP客户端配置"""
    timeout: int = 3600  # 默认超时时间1小时
    retry_count: int = 3  # 重试次数
    retry_delay: int = 1  # 重试延迟（秒）
    chunk_size: int = 8192  # 数据块大小

class HttpClient:
    """HTTP客户端封装"""
    def __init__(self, base_url: str, config: Optional[HttpConfig] = None):
        self.base_url = base_url.rstrip('/')
        self.config = config or HttpConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._timeout = aiohttp.ClientTimeout(
            total=self.config.timeout,
            connect=30,      
            sock_read=300,
            sock_connect=30  # 添加socket连接超时
        )
        # TCP连接配置
        self._connector = aiohttp.TCPConnector(
            force_close=False,
            enable_cleanup_closed=True,
            keepalive_timeout=60,
            limit=64  # 连接池大小，限制最大64个连接
        )

    async def __aenter__(self):
        await self.ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def ensure_session(self):
        """确保session已创建"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self._timeout,
                connector=self._connector,
                # 添加重试和超时的中间件
                raise_for_status=True
            )

    async def close(self):
        """关闭session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def request(self, method: str, endpoint: str, **kwargs) -> Union[Dict[str, Any], bytes, str]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        last_exception = None
        
        for attempt in range(self.config.retry_count):
            try:
                await self.ensure_session()
                kwargs['timeout'] = self._timeout
                
                async with self._session.request(method, url, **kwargs) as response:
                    response.raise_for_status()
                    
                    # 根据响应大小使用不同的读取策略
                    content_length = response.headers.get('Content-Length')
                    if content_length and int(content_length) > 1024 * 1024:  # 1MB
                        return await self._read_large_response(response)
                    else:
                        return await self._read_response(response)
                        
            except aiohttp.ClientError as e:
                last_exception = e
                retry_delay = self.config.retry_delay * (2 ** attempt)  # 指数退避
                logger.warning(f"Request attempt {attempt + 1} failed: {str(e)}, retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                await self.close()  # 确保关闭旧连接
                continue
                
        logger.error(f"Request failed after {self.config.retry_count} attempts: {str(last_exception)}")
        raise last_exception

    async def _read_large_response(self, response):
        """处理大型响应"""
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            return await response.json()
        else:
            # 分块读取大文件
            chunks = []
            async for chunk in response.content.iter_chunked(self.config.chunk_size):
                chunks.append(chunk)
            return b''.join(chunks)

    async def _read_response(self, response):
        """处理普通响应"""
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' in content_type:
            return await response.json()
        elif 'application/octet-stream' in content_type:
            return await response.read()
        else:
            return await response.text()

    async def get(self, endpoint: str, **kwargs) -> Union[Dict[str, Any], bytes, str]:
        """发送GET请求"""
        return await self.request('GET', endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> Union[Dict[str, Any], bytes, str]:
        """发送POST请求"""
        return await self.request('POST', endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> Union[Dict[str, Any], bytes, str]:
        """发送DELETE请求"""
        return await self.request('DELETE', endpoint, **kwargs) 