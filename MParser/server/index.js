require('dotenv').config(); // 加载 .env 文件中的配置
const express = require('express');
const cors = require('cors');
const fileUpload = require('express-fileupload');
const http = require('http');  // 添加 http 模块
const { SocketServer, LogLevel } = require('./Libs/SocketServer');  // 导入 SocketServer
const { initDatabase } = require('./Libs/DataBasePool');
const APIMaps = require('./APIs/APIMaps');
const app = express();

// 创建 HTTP 服务器
const server = http.createServer(app);

// 中间件配置
app.use(cors());
app.use(express.json({ limit: '100mb' }));
app.use(express.urlencoded({ limit: '100mb', extended: true }));
app.use(fileUpload({
    limits: { fileSize: 100 * 1024 * 1024 }, // 100MB
    abortOnLimit: true
}));

// 创建 SocketServer 实例
const socketServer = new SocketServer(server, {
    logLevel: LogLevel.DEBUG,
    corsOrigin: "*",
    pingTimeout: 10000,
    pingInterval: 5000
});

socketServer.registerBatch(APIMaps);

// 使用 SocketServer 的路由
app.use('/api', socketServer.getRouter());


// 路由配置
app.use('/nds', require('./APIs/NDS'));
app.use('/ndsfile', require('./APIs/NDSFile').router);
app.use('/node', require('./APIs/Node'));
app.use('/celldata', require('./APIs/CellData'));

// 启动服务器
async function startServer() {
    try {
        // 初始化数据库
        await initDatabase();
        
        // 启动服务器
        const port = process.env.PORT || 9002;
        server.listen(port, () => {  // 使用 server.listen 替代 app.listen
            console.log(`HTTP Server is running on port ${port}`);
            console.log(`Socket Server is running on port ${port}`);
        });
    } catch (error) {
        console.error('Failed to start server:', error);
        process.exit(1);
    }
}

// 处理未捕获的异常
process.on('uncaughtException', (error) => {
    console.error('Uncaught Exception:', error);
    process.exit(1);
});

process.on('unhandledRejection', (error) => {
    console.error('Unhandled Rejection:', error);
    process.exit(1);
});

startServer();
