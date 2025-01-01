# Socket API 通信框架

一个基于 Socket.IO 和 HTTP 的双模式异步通信框架，支持自动降级和并发控制。

## 安装依赖
```pip
pip install pydantic aiohttp python-socketio[client] 
```

## 使用说明

### 1. 创建客户端实例
```python
from SocketClient import SocketClient, LogLevel
client = SocketClient(
    socket_url="ws://localhost:3000",  # Socket服务器地址
    http_url="http://localhost:3000/api/call",  # HTTP降级地址（可选）
    callback_url="http://localhost:8000/api/callback",  # HTTP回调地址（可选）
    options={
        "log_level": LogLevel.INFO,  # 日志级别
        "max_concurrent": 10,  # 回调同时执行最大并发数
        "reconnection": True,  # 是否自动重连
        "reconnection_attempts": 3  # 重连尝试次数
    }
)
```



### 2. 定义回调处理函数
```python
async def handle_response(data: dict):
        print(f"收到响应数据: {data}")
```


### 3. 注册回调处理函数
```python
client.register_callback("api_name", handle_response)
```



### 4. 调用API
```python
# 连接服务器
    await client.connect_to_server()

    # 发送请求
    result = await client.call_api(
        api="api_name",           # API名称
        data={"param": "value"},  # 请求参数
        callback_func="api_name"  # 回调处理函数名称
    )
    
    # 断开连接
    await client.disconnect()
```

    


## 配置选项说明
| 选项                     | 说明        | 默认值           |
|------------------------|-----------|---------------|
| log_level              | 日志输出级别    | LogLevel.INFO |
| max_concurrent         | 回调处理最大并发数 | 10            |
| reconnection           | 是否自动重连    | True          |
| reconnection_attempts  | 重连尝试次数    | 3             |
| reconnection_delay     | 重连延迟(秒)   | 1             |
| reconnection_delay_max | 最大重连延迟(秒) | 5             |

## 通信模式

### 1. Socket模式（默认）
- 使用 WebSocket 进行实时通信
- 支持自动重连
- 不需要配置 http_url 和 callback_url

### 2. HTTP降级模式
- Socket连接失败时自动启用
- 需要配置 http_url 和 callback_url
- 通过回调接口接收响应

## 错误处理

```python
try:
    result = await client.call_api(...)
except ConnectionError as e:
    print("连接失败:", e)
except ValueError as e:
    print("参数错误:", e)
except Exception as e:
    print("其他错误:", e)
```



## 注意事项
* 回调处理函数必须是异步函数（async def）
* 使用前需要先调用 connect_to_server()
* 程序结束前建议调用 disconnect()
* HTTP降级模式需要同时配置 http_url 和 callback_url
* 回调函数需要在调用API前注册 

## 示例代码 - 使用FastAPI 实现HTTP回调接收接口
```python

import uvicorn
from typing import Dict
from SocketClient import SocketClient, LogLevel
from fastapi import FastAPI, HTTPException, Request
from contextlib import asynccontextmanager


# 定义回调处理函数
async def handle_user_get(data: Dict):
    """处理用户查询响应"""
    return data

async def handle_user_update(data: Dict):
    """处理用户更新响应"""
    return data



@asynccontextmanager
async def lifespan(_: FastAPI):
    # 启动时
    app.state.socket_client = SocketClient(
        socket_url="ws://localhost:3000",  # Socket连接地址
        http_url="http://localhost:3000/api/call",  # HTTP降级地址
        callback_url="http://localhost:8000/api/callback",  # HTTP回调地址
        options={
            "log_level": LogLevel.INFO,
        }
    )
    # 注册回调处理函数
    app.state.socket_client.register_callback("user.get", handle_user_get)
    app.state.socket_client.register_callback("user.update", handle_user_update)
    
    # 连接到服务器
    await app.state.socket_client.connect_to_server()

    yield
    
    # 关闭时
    await app.state.socket_client.disconnect()
    app.state.socket_client = None

app = FastAPI(lifespan=lifespan)


# HTTP回调接口 - 使用固定路径
@app.post("/api/callback")
async def http_callback(request: Request):
    """处理HTTP回调 - 非阻塞"""
    try:
        data = await request.json()
        return await app.state.socket_client.handle_callback(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 测试API调用
@app.post("/api/call")
async def call_api(request: Request):
    """API调用入口"""
    try:
        body = await request.json()
        
        # 从请求中获取参数
        api_request = {
            "api": body.get("api"),
            "data": body.get("data"),
            "callback_type": body.get("callback_type", "socket"),
            "callback_func": body.get("callback_func"),
            "request_id": body.get("request_id")
        }
        
        result = await app.state.socket_client.call_api(**api_request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))  # API调用失败


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 
```