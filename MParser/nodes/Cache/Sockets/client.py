import asyncio
import json


class SocketClient:
    def __init__(self, host: str = '127.0.0.1', port: int = 10003):
        self.host = host
        self.port = port

    async def start(self):
        """启动客户端"""
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
            # 创建两个并行任务：一个处理服务器消息，一个处理用户输入
            await asyncio.gather(
                self.handle_server_messages(reader),
                self.handle_commands(writer)
            )
        except Exception as e:
            print(f"Error connecting to server: {e}")

    async def handle_server_messages(self, reader: asyncio.StreamReader):
        """处理来自服务器的消息"""
        while True:
            try:
                # 读取消息长度（4字节）
                length_bytes = await reader.read(4)
                if not length_bytes:
                    break

                msg_length = int.from_bytes(length_bytes, 'big')
                # 读取消息内容
                data = await reader.read(msg_length)
                if not data:
                    break

                # 输出服务器发送的消息
                message = json.loads(data.decode())
                print(f"Received from server: {message}")
            except Exception as e:
                print(f"Error receiving message: {e}")
                break

    async def handle_commands(self, writer: asyncio.StreamWriter):
        """处理命令行输入"""
        loop = asyncio.get_event_loop()
        try:
            while True:
                # 使用线程执行器运行阻塞的input操作
                message = await loop.run_in_executor(None, input, "Enter message: ")
                data = json.dumps({"message": message}).encode()
                writer.write(len(data).to_bytes(4, 'big') + data)
                await writer.drain()
                print("Message sent.")
        except Exception as e:
            print(f"Error sending message: {e}")
        finally:
            writer.close()
            await writer.wait_closed()


async def main():
    client = SocketClient()
    await client.start()

if __name__ == "__main__":
    asyncio.run(main())
