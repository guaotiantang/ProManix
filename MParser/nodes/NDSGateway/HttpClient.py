import aiohttp
import logging
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HttpConfig:
    """HTTP客户端配置"""
    timeout: int = 3600  # 默认超时时间1小时


class HttpClient:
    """HTTP客户端封装"""

    def __init__(self, base_url: str, config: Optional[HttpConfig] = None):
        self.base_url = base_url.rstrip('/')
        self.config = config or HttpConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._timeout = aiohttp.ClientTimeout(total=self.config.timeout)

    async def __aenter__(self):
        await self.ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def ensure_session(self):
        """确保session已创建"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self._timeout)

    async def close(self):
        """关闭session"""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def request(
            self,
            method: str,
            endpoint: str,
            **kwargs
    ) -> Union[Dict[str, Any], bytes, str]:
        """发送HTTP请求"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        await self.ensure_session()

        try:
            async with self._session.request(method, url, **kwargs) as response:
                response.raise_for_status()

                content_type = response.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    return await response.json()
                elif 'application/octet-stream' in content_type:
                    return await response.read()
                else:
                    return await response.text()
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            raise

    async def get(self, endpoint: str, **kwargs) -> Union[Dict[str, Any], bytes, str]:
        """发送GET请求"""
        return await self.request('GET', endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> Union[Dict[str, Any], bytes, str]:
        """发送POST请求"""
        return await self.request('POST', endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> Union[Dict[str, Any], bytes, str]:
        """发送DELETE请求"""
        return await self.request('DELETE', endpoint, **kwargs)
