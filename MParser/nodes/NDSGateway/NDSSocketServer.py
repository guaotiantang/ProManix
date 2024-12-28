import asyncio
import json
import logging
from typing import Dict, Any
from NDSApi import nds_api

logger = logging.getLogger(__name__)

class NDSSocketServer:
    """NDS Socket服务器
    
    提供异步socket接口，支持NDS操作的调用和回调
    """
    def __init__(self, host: str = '0.0.0.0', port: int = 10003):
        self.host = host
        self.port = port
        self.server = None
        self._clients: Dict[str, asyncio.StreamWriter] = {}
        
    async def start(self):
        """启动socket服务器"""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        logger.info(f"Socket server started on {self.host}:{self.port}")
        
    async def stop(self):
        """停止socket服务器"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            # 关闭所有客户端连接
            for writer in self._clients.values():
                writer.close()
                await writer.wait_closed()
            self._clients.clear()
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理客户端连接"""
        peer = writer.get_extra_info('peername')
        client_id = f"{peer[0]}:{peer[1]}"
        self._clients[client_id] = writer
        
        try:
            while True:
                # 读取消息长度（4字节）
                length_bytes = await reader.read(4)
                if not length_bytes:
                    break
                    
                msg_length = int.from_bytes(length_bytes, 'big')
                # 读取消息内容
                data = await reader.read(msg_length)
                if not data:
                    break
                    
                # 解析消息
                try:
                    message = json.loads(data.decode())
                    response = await self.handle_message(message)
                    # 发送响应
                    await self.send_response(writer, response)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from {client_id}")
                    await self.send_response(writer, {
                        "error": "Invalid JSON format"
                    })
                    
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            del self._clients[client_id]
            
    async def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """处理接收到的消息"""
        try:
            action = message.get('action')
            if not action:
                return {"error": "Missing action"}
                
            if action == "scan":
                # 处理扫描请求
                result = await self._handle_scan(message)
                return {"action": "scan_result", "data": result}
                
            elif action == "zip_info":
                # 处理ZIP信息请求
                result = await self._handle_zip_info(message)
                return {"action": "zip_info_result", "data": result}
                
            elif action == "update_pool":
                # 处理连接池更新
                result = await self._handle_update_pool(message)
                return {"action": "update_result", "data": result}
                
            else:
                return {"error": f"Unknown action: {action}"}
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            return {"error": str(e)}
            
    async def _handle_scan(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """处理扫描请求"""
        try:
            nds_id = message.get('nds_id')
            scan_path = message.get('scan_path')
            filter_pattern = message.get('filter_pattern')
            
            if not nds_id or not scan_path:
                return {"error": "Missing required parameters"}
                
            async with nds_api.pool.get_client(str(nds_id)) as client:
                files = await client.scan(scan_path, filter_pattern)
                return {"files": files}
                
                    
        except Exception as e:
            logger.error(f"Scan error: {e}")
            return {"error": str(e)}
            
    async def _handle_zip_info(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """处理ZIP信息请求"""
        try:
            nds_id = message.get('nds_id')
            file_paths = message.get('file_paths', [])
            
            if not nds_id or not file_paths:
                return {"error": "Missing required parameters"}
                
            async with nds_api.pool.get_client(str(nds_id)) as client:
                zip_infos = {}
                for file_path in file_paths:
                    try:
                        result = await client.get_zip_info(file_path)
                        zip_infos[file_path] = {
                            "status": "success",
                            "info": result
                        }
                    except Exception as e:
                        zip_infos[file_path] = {
                            "status": "error",
                            "error": str(e)
                        }
                return {"zip_infos": zip_infos}
                    
        except Exception as e:
            logger.error(f"ZIP info error: {e}")
            return {"error": str(e)}
            
    async def _handle_update_pool(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """处理连接池更新"""
        try:
            action = message.get('action')
            config = message.get('config')
            
            if not action or not config:
                return {"error": "Missing action or config"}
                
            result = await nds_api.pool.update_pool(action, config)
            return result
            
        except Exception as e:
            logger.error(f"Update pool error: {e}")
            return {"error": str(e)}
            
    async def send_response(self, writer: asyncio.StreamWriter, response: Dict[str, Any]):
        """发送响应给客户端"""
        try:
            # 编码响应
            data = json.dumps(response).encode()
            # 发送数据长度
            writer.write(len(data).to_bytes(4, 'big'))
            # 发送数据内容
            writer.write(data)
            await writer.drain()
        except Exception as e:
            logger.error(f"Error sending response: {e}")
            
    async def broadcast(self, message: Dict[str, Any]):
        """广播消息给所有连接的客户端"""
        for writer in self._clients.values():
            try:
                await self.send_response(writer, message)
            except Exception as e:
                logger.error(f"Broadcast error: {e}") 