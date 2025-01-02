import uuid
import aiohttp
import logging
import socketio
from typing import Dict, Any, Callable, Literal
from pydantic import BaseModel
from urllib.parse import urlparse
import asyncio


# 定义日志级别
class LogLevel:
    ERROR = logging.ERROR  # 只输出错误
    WARN = logging.WARN  # 输出警告和错误
    INFO = logging.INFO  # 输出一般信息、警告和错误
    DEBUG = logging.DEBUG  # 输出所有信息


class ApiRequest(BaseModel):
    api: str  # 调用的API名称
    data: Dict[str, Any]  # API参数
    callback_type: Literal["socket", "http"] = "socket"  # 回调方式
    callback_url: str | None = None  # HTTP接收回调数据接口
    callback_func: str  # 回调处理接口名称
    request_id: str | None = None  # 请求ID，默认为 None

    def __init__(self, **data):
        super().__init__(**data)
        # 如果没有提供 request_id，则生成一个新的
        if not self.request_id:
            self.request_id = str(uuid.uuid4())


# noinspection HttpUrlsUsage
class SocketClient:
    def __init__(self, socket_url: str, http_url: str = None, callback_url: str = None, options: dict = None):
        """初始化Socket客户端
        
        Args:
            socket_url (str): Socket服务器URL (ws://hostname:port)
            http_url (str, optional): HTTP服务器URL (http://hostname:port)，用于Socket连接失败时的HTTP降级
            callback_url (str, optional): HTTP回调URL (http://hostname:port/path)，不设置则不使用HTTP降级
            options (dict, optional): 配置选项. 默认{
                "reconnection": True,  # 是否自动重连
                "reconnection_attempts": 3,  # 重连次数
                "reconnection_delay": 1,  # 重连延迟
                "reconnection_delay_max": 5,  # 最大重连延迟
                "logger": False,  # 是否启用日志
                "engineio_logger": False,  # 是否启用引擎日志
                "log_level": LogLevel.INFO,  # 日志级别
                "max_concurrent": 10  # 回调同时执行最大并发数
            }.
        """
        options = options or {}
        # 设置日志级别
        self.log_level = options.get("log_level", LogLevel.INFO)
        logging.getLogger().setLevel(self.log_level)

        # 创建异步socketio客户端
        self.sio = socketio.AsyncClient(
            reconnection=options.get("reconnection", True),
            reconnection_attempts=options.get("reconnection_attempts", -1),
            reconnection_delay=options.get("reconnection_delay", 1),
            reconnection_delay_max=options.get("reconnection_delay_max", 5),
            logger=options.get("logger", False),
            engineio_logger=options.get("engineio_logger", False)
        )

        self.socket_url = socket_url
        self.http_url = http_url
        self.callback_url = callback_url
        self._callback_path = self._parse_callback_path(callback_url) if callback_url else None
        self._connected = False
        self._http_session = None
        self._callback_handlers = {}
        self._manual_disconnect = False  # 标记是否为手动断开
        self.setup_handlers()

        # 添加并发控制
        self._max_concurrent = options.get("max_concurrent", 10)
        self._callback_semaphore = asyncio.Semaphore(self._max_concurrent)

    @staticmethod
    def _parse_callback_path(url: str) -> str:
        """从完整URL中提取回调路径"""
        parsed = urlparse(url)
        return parsed.path or '/'

    @property
    def callback_path(self) -> str:
        """获取回调路径"""
        return self._callback_path

    def register_callback(self, name: str, handler: Callable):
        """注册回调处理函数"""
        self._callback_handlers[name] = handler
        return self

    async def _handle_callback_with_limit(self, data: Dict):
        """使用信号量限制并发的回调处理"""
        async with self._callback_semaphore:
            callback_func = data.get('callback_func')
            if callback_func and callback_func in self._callback_handlers:
                # 执行回调处理函数
                await self._callback_handlers[callback_func](data)
                return {"success": True, "message": "回调处理完成"}
            else:
                self.log(LogLevel.WARN, f"未找到回调处理函数: {callback_func}")
                return {"success": False, "message": f"未找到回调处理函数: {callback_func}"}

    async def handle_callback(self, data: Dict):
        """异步回调处理函数"""
        try:
            # 创建限制并发的回调任务
            asyncio.create_task(self._handle_callback_with_limit(data))
            return {"success": True, "message": "回调任务已创建"}
        except Exception as e:
            self.log(LogLevel.ERROR, "回调处理失败", e)
            return {"success": False, "message": str(e)}

    def log(self, level: int, message: str, error: Exception = None):
        """统一的日志输出"""
        if level >= self.log_level:
            if error:
                logging.log(level, f"{message}: {error}")
            else:
                logging.log(level, message)

    def setup_handlers(self):
        """设置事件处理函数"""

        @self.sio.event
        async def connect():
            self._connected = True
            self.log(LogLevel.INFO, "Socket连接成功")

        @self.sio.event
        async def disconnect():
            self._connected = False
            if not self._manual_disconnect:
                self.log(LogLevel.INFO, "Socket连接断开，尝试重连...")
                try:
                    await self.connect_to_server()
                except Exception as e:
                    self.log(LogLevel.ERROR, "重连失败", e)
            else:
                self.log(LogLevel.INFO, "Socket连接已断开")

        @self.sio.event
        async def connect_error(data):
            self._connected = False
            self.log(LogLevel.ERROR, f"Socket连接错误: {data}")

        @self.sio.on('apiResponse')
        async def on_api_response(data):
            """处理Socket回调"""
            await self.handle_callback(data)

    async def _ensure_http_session(self):
        """确保HTTP会话可用"""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()

    async def call_api(self, api: str, data: Dict[str, Any], callback_type: str = "socket",
                       callback_func: str = None, request_id: str = None) -> Dict:
        """
        调用API并处理响应
        :param api: API名称
        :param data: API参数
        :param callback_type: 回调类型，可选 "socket" 或 "http"
        :param callback_func: 回调处理接口名称
        :param request_id: 请求ID
        :return: 请求确认信息
        """
        if callback_func and callback_func not in self._callback_handlers:
            raise ValueError(f"未注册的回调处理函数: {callback_func}")

        request = ApiRequest(
            api=api,
            data=data,
            callback_type=callback_type,
            callback_url=self.callback_url,
            callback_func=callback_func or api,
            request_id=request_id
        )

        try:
            # 如果是HTTP模式，直接使用HTTP
            if callback_type.lower() == "http" and self.http_url and self.callback_url:
                await self._ensure_http_session()
                async with self._http_session.post(
                        self.http_url,
                        json=request.model_dump(),
                        headers={'Content-Type': 'application/json'}
                ) as response:
                    return await response.json()

            # Socket模式
            if not self._connected:
                await self.connect_to_server()

            # 使用Socket发送
            try:
                await self.sio.emit('api', request.model_dump())
                return {
                    'success': True,
                    'message': '请求已通过Socket发送',
                    'request_id': request.request_id
                }
            except Exception as e:
                self.log(LogLevel.ERROR, "Socket发送失败", e)
                if self.http_url and self.callback_url:
                    request.callback_type = "http"
                    await self._ensure_http_session()
                    async with self._http_session.post(
                            self.http_url,
                            json=request.model_dump(),
                            headers={'Content-Type': 'application/json'}
                    ) as response:
                        return await response.json()
                else:
                    raise

        except Exception as e:
            self.log(LogLevel.ERROR, "API调用失败", e)
            raise

    async def connect_to_server(self):
        """连接到Socket服务器"""
        try:
            if not self.sio.connected:
                await self.sio.connect(self.socket_url)  # 使用WebSocket URL
        except Exception as e:
            logging.error(f"Socket服务器连接失败: {e}")
            self._connected = False
            raise

    async def disconnect(self):
        """断开连接"""
        try:
            self._manual_disconnect = True  # 标记为手动断开
            if self.sio.connected:
                await self.sio.disconnect()
            if self._http_session and not self._http_session.closed:
                await self._http_session.close()
        except Exception as e:
            self.log(LogLevel.ERROR, "断开连接时发生错误", e)
        finally:
            self._manual_disconnect = False  # 重置标记

    @property
    def is_connected(self) -> bool:
        return self._connected
