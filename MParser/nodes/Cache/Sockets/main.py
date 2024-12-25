import asyncio
import json
from typing import Dict


class SocketServer:
    def __init__(self, host: str = '0.0.0.0', port: int = 10003):
        self.host = host
        self.port = port
        self.server = None
        self._clients: Dict[str, asyncio.StreamWriter] = {}

    async def start(self):
        """启动服务器"""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port
        )
        print(f"Server started on {self.host}:{self.port}")
        # 在单独的线程中处理命令行输入
        asyncio.create_task(self.handle_commands())

    async def stop(self):
        """停止服务器"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            # 关闭所有客户端连接
            for writer in self._clients.values():
                writer.close()
                await writer.wait_closed()
            self._clients.clear()
        print("Server stopped.")

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """处理客户端连接"""
        peer = writer.get_extra_info('peername')
        client_id = f"{peer[0]}:{peer[1]}"
        self._clients[client_id] = writer
        print(f"Client {client_id} connected.")

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
                    print(f"Received from {client_id}: {message}")
                except json.JSONDecodeError:
                    print(f"Invalid JSON from {client_id}")
        except Exception as e:
            print(f"Error handling client {client_id}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            del self._clients[client_id]
            print(f"Client {client_id} disconnected.")

    async def handle_commands(self):
        """处理命令行输入"""
        loop = asyncio.get_event_loop()
        while True:
            # 使用线程执行器运行阻塞的input操作
            cmd = await loop.run_in_executor(None, input, "Enter command (client_id:message): ")
            if ":" in cmd:
                client_id, message = cmd.split(":", 1)
                if client_id in self._clients:
                    await self.send_message(self._clients[client_id], message)
                else:
                    print(f"Client {client_id} not connected.")
            else:
                print("Invalid command format. Use client_id:message.")

    async def send_message(self, writer: asyncio.StreamWriter, message: str):
        """向客户端发送消息"""
        data = json.dumps({"message": message}).encode()
        writer.write(len(data).to_bytes(4, 'big') + data)
        await writer.drain()
        print(f"Sent to client: {message}")


async def main():
    server = SocketServer()
    try:
        await server.start()
        await server.server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping server...")
        await server.stop()

if __name__ == "__main__":
    asyncio.run(main())
