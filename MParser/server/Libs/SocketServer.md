# Socket API 服务端框架

一个基于 Socket.IO 和 HTTP 的双模式异步通信服务端框架，支持 Socket 和 HTTP 双模式请求处理。

## 安装依赖
### npm
```bash
npm install socket.io express axios
```
### yarn
```bash
yarn add socket.io express axios
```


## 使用说明

### 1. 创建服务端实例
```javascript
const SocketServer = require('./SocketServer');
const express = require('express');
const http = require('http');

const app = express();
const server = http.createServer(app);

const socketServer = new SocketServer(server, {
    logLevel: LogLevel.INFO,     // 日志级别
    corsOrigin: "*",             // CORS配置
    pingTimeout: 10000,          // 心跳超时
    pingInterval: 5000           // 心跳间隔
});
```

### 2. 定义API处理函数
```javascript
async function handleUserGet(data) {
    const { userId } = data;
    // 处理逻辑
    return {
        success: true,
        data: { id: userId, name: "Test User" }
    };
}

async function handleUserUpdate(data) {
    const { userId, name } = data;
    // 处理逻辑
    return {
        success: true,
        data: { id: userId, name }
    };
}
```

### 3. 注册API处理函数
```javascript
socketServer.registerHandler("user.get", handleUserGet);
socketServer.registerHandler("user.update", handleUserUpdate);
```

### 4. 启动服务器
```javascript
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
```

## 配置选项说明
| 选项           | 说明       | 默认值           |
|--------------|----------|---------------|
| logLevel     | 日志输出级别   | LogLevel.INFO |
| corsOrigin   | CORS配置   | "*"           |
| pingTimeout  | 心跳超时(ms) | 10000         |
| pingInterval | 心跳间隔(ms) | 5000          |

## 通信模式

### 1. Socket模式（默认）
- 客户端通过 Socket.IO 连接
- 支持实时双向通信
- 自动处理重连和心跳

### 2. HTTP模式
- 通过 HTTP POST 请求调用 API
- 支持同步响应或异步回调
- 需要配置回调地址进行异步通知

## 错误处理
```javascript
try {
    const result = await handleUserGet(data);
    return { success: true, data: result };
} catch (error) {
    return { 
        success: false, 
        error: error.message 
    };
}
```

## 注意事项
* API处理函数必须是异步函数（async）
* 处理函数返回格式必须包含 success 字段
* HTTP模式下需要正确处理回调通知
* 建议在处理函数中进行异常捕获
* 回调通知会自动重试直到成功

## 示例代码 - 完整服务端实现
```javascript
const express = require('express');
const http = require('http');
const SocketServer = require('./SocketServer');

// 创建Express应用
const app = express();
const server = http.createServer(app);

// 创建Socket服务器
const socketServer = new SocketServer(server, {
    logLevel: LogLevel.INFO,
    corsOrigin: "*"
});

// API处理函数
async function handleUserGet(data) {
    const { userId } = data;
    return {
        success: true,
        data: { id: userId, name: "Test User" }
    };
}

async function handleUserUpdate(data) {
    const { userId, name } = data;
    return {
        success: true,
        data: { id: userId, name }
    };
}

// 注册API处理函数
socketServer.registerHandler("user.get", handleUserGet);
socketServer.registerHandler("user.update", handleUserUpdate);

// HTTP路由
app.post('/api/call', express.json(), async (req, res) => {
    try {
        const result = await socketServer.handleHttpRequest(req.body);
        res.json(result);
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message
        });
    }
});

// 启动服务器
const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
``` 