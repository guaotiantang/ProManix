require('dotenv').config(); // 加载 .env 文件中的配置
const express = require('express');
const cors = require('cors');
const fileUpload = require('express-fileupload');
const { initDatabase } = require('./Libs/DataBasePool');

const app = express();

// 中间件配置
app.use(cors());
app.use(express.json());
app.use(fileUpload());

// 路由配置
app.use('/api/nds', require('./APIs/NDS'));
app.use('/api/ndsfile', require('./APIs/NDSFile'));
app.use('/api/node', require('./APIs/Node'));
app.use('/api/celldata', require('./APIs/CellData'));

// 启动服务器
async function startServer() {
    try {
        // 初始化数据库
        await initDatabase();
        
        // 启动服务器
        const port = process.env.PORT || 9002;
        app.listen(port, () => {
            console.log(`Server is running on port ${port}`);
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
