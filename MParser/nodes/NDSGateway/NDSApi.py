from fastapi import APIRouter, HTTPException, Body, Response, WebSocket, WebSocketDisconnect
from typing import Dict, List, Any, Optional
from NDSPool import NDSPool, PoolConfig
from HttpClient import HttpClient
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nds", tags=["NDS"])


class NDSApi:
    def __init__(self):
        self.pool = NDSPool()
        self.backend_client = None

    async def init_api(self, backend_url: str):
        """初始化API"""
        self.backend_client = HttpClient(backend_url)
        await self.init_pool()

    async def init_pool(self):
        """初始化连接池"""
        try:
            data = await self.backend_client.get("nds/list")
            if not data:
                return

            for nds in data.get('list', []):
                if nds['Switch'] == 1:
                    pool_config = PoolConfig(
                        protocol=nds['Protocol'],
                        host=nds['Address'],
                        port=nds['Port'],
                        user=nds['Account'],
                        passwd=nds['Password']
                    )
                    self.pool.add_server(str(nds['ID']), pool_config)
            print("Add NDSPool Count:", len(data.get('list', [])))
        except Exception as e:
            logger.error(f"Failed to initialize pool: {e}")

    async def close(self):
        """关闭资源"""
        await self.pool.close()
        if self.backend_client:
            await self.backend_client.close()


# 创建全局实例
nds_api = NDSApi()


# 请求模型
class ReadFileRequest(BaseModel):
    """读取文件请求模型"""
    NDSID: int
    FilePath: str
    HeaderOffset: Optional[int] = 0
    CompressSize: Optional[int] = None


@router.post("/update-pool")
async def update_pool(data: Dict[str, Any] = Body(...)) -> Dict[str, str]:
    """更新连接池配置"""
    try:
        action = data.get('action')
        config = data.get('config', {})

        if not action or not config:
            raise HTTPException(status_code=400, detail="Missing action or config")

        if action not in ['add', 'update', 'remove']:
            raise HTTPException(status_code=400, detail="Invalid action")

        if not isinstance(config, dict):
            raise HTTPException(status_code=400, detail="Invalid config format")

        # 处理删除操作
        if action == "remove":
            if 'ID' not in config:
                raise HTTPException(status_code=400, detail="Missing ID in config")
            await nds_api.pool.remove_server(str(config['ID']))
            return {"message": "Server removed"}

        # 处理添加和更新操作
        required_fields = ['ID', 'Switch', 'Protocol', 'Address', 'Port', 'Account', 'Password']
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )

        # 如果Switch为0，执行删除操作
        if config['Switch'] != 1:
            await nds_api.pool.remove_server(str(config['ID']))
            return {"message": "Server removed due to Switch off"}

        # 创建连接池配置
        pool_config = PoolConfig(
            protocol=config['Protocol'],
            host=config['Address'],
            port=config['Port'],
            user=config['Account'],
            passwd=config['Password']
        )

        # 执行相应操作
        if action == "add":
            nds_api.pool.add_server(str(config['ID']), pool_config)
        else:  # update
            await nds_api.pool.remove_server(str(config['ID']))
            nds_api.pool.add_server(str(config['ID']), pool_config)

        return {"message": f"Server {action}ed successfully"}

    except Exception as e:
        logger.error(f"Update pool error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan")
async def scan_files(data: dict = Body(...)) -> List[str]:
    """扫描文件"""
    try:
        nds_id = data.get('nds_id')
        scan_path = data.get('scan_path')
        filter_pattern = data.get('filter_pattern')

        if not nds_id or not scan_path:
            raise HTTPException(status_code=400, detail="Missing required parameters")

        async with nds_api.pool.get_client(str(nds_id)) as client:
            return await client.scan(scan_path, filter_pattern)
    except Exception as e:
        logger.error(f"NDS[{data.get('nds_id')}]Scan files error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_pool_status() -> Dict:
    """获取连接池状态"""
    try:
        return nds_api.pool.get_all_pool_status()
    except Exception as e:
        logger.error(f"Get pool status error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/zip-info")
async def get_zip_info(data: dict = Body(...)):
    """获取多个ZIP文件的信息"""
    try:
        nds_id = data.get('nds_id')
        file_paths = data.get('file_paths', [])

        if not nds_id or not file_paths:
            raise HTTPException(status_code=400, detail="Missing required parameters")
        
        async with nds_api.pool.get_client(str(nds_id)) as client:
            zip_infos = {}
            for file_path in file_paths:
                try:
                    result = await client.get_zip_info(file_path)
                    zip_infos[file_path] = {
                        "status": "success",
                        "info": [
                            {
                                "file_name": info.file_name,
                                "sub_file_name": info.sub_file_name,
                                "directory": info.directory,
                                "header_offset": int(info.header_offset),
                                "compress_size": int(info.compress_size),
                                "file_size": int(info.file_size),
                                "flag_bits": int(info.flag_bits),
                                "compress_type": int(info.compress_type),
                                "enodebid": int(info.enodebid)
                            }
                            for info in result
                        ]
                    }
                except Exception as e:
                    zip_infos[file_path] = {
                        "status": "error",
                        "error": str(e)
                    }
                    logger.error(f"Error processing {file_path}: {e}")

            return {
                "code": 200,
                "data": zip_infos
            }

    except Exception as e:
        logger.error(f"Get ZIP info error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/read")
async def read_file(request: ReadFileRequest) -> Response:
    """读取NDS文件内容
    
    Args:
        request: 包含以下字段的请求体
            - NDSID: NDS服务器ID
            - FilePath: 文件路径
            - HeaderOffset: 文件头偏移量（可选，默认0）
            - CompressSize: 要读取的字节数（可选，默认读取到文件末尾）
            
    Returns:
        Response: 二进制响应，包含文件内容
        响应头包含：
        - Content-Type: application/octet-stream
        - Content-Length: 文件大小
        - X-File-Size: 文件大小
    """
    try:
        # 检查NDS服务器是否已配置
        if str(request.NDSID) not in nds_api.pool.get_server_ids():
            raise HTTPException(
                status_code=403,
                detail=f"NDS服务器 {request.NDSID} 未配置"
            )

        # 获取NDS客户端连接
        async with nds_api.pool.get_client(str(request.NDSID)) as client:
            # 读取文件内容
            content = await client.read_file_bytes(
                file_path=request.FilePath,
                header_offset=request.HeaderOffset or 0,
                size=request.CompressSize
            )
            
            # 直接返回二进制内容
            return Response(
                content=content,
                media_type="application/octet-stream",
                headers={
                    "Content-Length": str(len(content)),
                    "X-File-Size": str(len(content))
                }
            )
            
    except FileNotFoundError:
        
        raise HTTPException(
            status_code=404,
            detail=f"文件不存在: {request.FilePath}"
        )
    except Exception as e:
        print("Read Error")
        logger.error(f"读取文件失败: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"读取文件失败: {str(e)}"
        )


# 添加 WebSocket 管理器
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]

    async def send_bytes(self, client_id: str, data: bytes):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_bytes(data)

manager = ConnectionManager()

@router.websocket("/ws/read/{client_id}")
async def websocket_read(websocket: WebSocket, client_id: str):
    """WebSocket读取文件接口"""
    CHUNK_SIZE = 512 * 1024  # 512KB chunks
    await manager.connect(websocket, client_id)
    try:
        # 等待接收读取文件的请求
        data = await websocket.receive_json()
        # 检查NDS服务器是否已配置
        if str(data['NDSID']) not in nds_api.pool.get_server_ids():
            await websocket.send_json({
                "code": 403,
                "message": f"NDS服务器 {data['NDSID']} 未配置"
            })
            return

        # 获取NDS客户端连接并读取文件
        try:
            content = None
            async with nds_api.pool.get_client(str(data['NDSID'])) as client:
                content = await client.read_file_bytes(
                    file_path=data['FilePath'],
                    header_offset=data.get('HeaderOffset', 0),
                    size=data.get('CompressSize')
                )
                if not await client.check_connect():
                    print("No Connected")
            
            if content is None:
                raise Exception("Data is null")
            
            # 使用分块传输发送数据
            for i in range(0, len(content), CHUNK_SIZE):
                chunk = content[i:i + CHUNK_SIZE]
                await websocket.send_bytes(chunk)
            
            # 发送结束标记
            await websocket.send_json({"end_of_file": True})
                
        except FileNotFoundError:
            await websocket.send_json({
                "code": 404,
                "message": f"文件不存在: {data['FilePath']}"
            })
        except Exception as e:
            await websocket.send_json({
                "code": 500,
                "message": str(e)
            })
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # 其他错误，尝试发送错误消息
        try:
            await websocket.send_json({
                "code": 500,
                "message": f"处理请求时发生错误: {str(e)}"
            })
        except:
            pass
    finally:
        # 断开WebSocket连接
        try:
            manager.disconnect(client_id)
        except Exception:
            pass

