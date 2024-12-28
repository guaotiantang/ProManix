import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()



# 配置
NODE_TYPE = os.getenv('NODE_TYPE', 'ParserNode')
SERVICE_NAME = os.getenv('SERVICE_NAME')
BACKEND_URL = os.getenv('BACKEND_URL')
SERVICE_HOST = os.getenv('SERVICE_HOST')
SERVICE_PORT = int(os.getenv('SERVICE_PORT', 10003))
BACKEND_URL = os.getenv('BACKEND_URL')
NDS_GATEWAY_URL = os.getenv('NDS_GATEWAY_URL')

