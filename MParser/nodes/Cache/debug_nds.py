import asyncio
import asyncssh
import logging
from typing import List

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NDSDebugger:
    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = None
        self.sftp = None

    async def connect(self):
        """建立连接"""
        try:
            self.client = await asyncssh.connect(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                known_hosts=None
            )
            self.sftp = await self.client.start_sftp_client()
            logger.info(f"Successfully connected to {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise

    async def test_commands(self):
        """测试各种SFTP命令"""
        if not self.sftp:
            logger.error("Not connected")
            return

        commands = [
            ("realpath('/')", lambda: self.sftp.realpath('/')),
            ("realpath(b'/')", lambda: self.sftp.realpath(b'/')),
            ("stat('/')", lambda: self.sftp.stat('/')),
            ("stat('.')", lambda: self.sftp.stat('.')),
            ("lstat('.')", lambda: self.sftp.lstat('.')),
            ("getcwd()", lambda: self.sftp.getcwd()),
            ("listdir('/')", lambda: self.sftp.listdir('/')),
            ("scandir('/')", lambda: self.sftp.scandir('/')),
        ]

        results = []
        for name, cmd in commands:
            try:
                result = await cmd()
                logger.info(f"✅ {name} succeeded: {result}")
                results.append((name, True, str(result)))
            except Exception as e:
                logger.error(f"❌ {name} failed: {e}")
                results.append((name, False, str(e)))

        return results

    async def close(self):
        """关闭连接"""
        if self.sftp:
            self.sftp.exit()
        if self.client:
            self.client.close()
            await self.client.wait_closed()

async def main():
    # 配置你的服务器信息
    config = {
        'host': 'your_host',
        'port': 22,  # 默认SFTP端口
        'username': 'your_username',
        'password': 'your_password'
    }

    debugger = NDSDebugger(**config)
    try:
        await debugger.connect()
        results = await debugger.test_commands()
        
        # 打印汇总报告
        print("\n=== 测试结果汇总 ===")
        for name, success, result in results:
            status = "✅ 支持" if success else "❌ 不支持"
            print(f"{status} {name}")
            if success:
                print(f"   结果: {result}")
            else:
                print(f"   错误: {result}")
            print("-" * 50)

    except Exception as e:
        logger.error(f"Debug session failed: {e}")
    finally:
        await debugger.close()

if __name__ == "__main__":
    asyncio.run(main()) 