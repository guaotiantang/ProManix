require('dotenv').config(); // 加载 .env 文件中的配置
const express = require('express');
const cors = require('cors');
const cookieParser = require('cookie-parser');
const bodyParser = require('body-parser');
const {sequelize, checkConnection} = require("./Libs/DataBasePool");
const path = require('path');
const fileUpload = require('express-fileupload');
const cellDataRouter = require('./APIs/CellData');
const ndsRouter = require('./APIs/NDS');
const nodeRouter = require('./APIs/Node');

const app = express();
app.use(express.json({limit: '50mb'}));
app.use(express.urlencoded({limit: '50mb', extended: true}));
app.use(bodyParser.json({limit: '50mb'}));
app.use(bodyParser.urlencoded({limit: '50mb', extended: true}));

app.use(cookieParser()); //启用Cookies插件
app.use(cors({
    origin: '*',
    credentials: true,
}));



// 添加文件上传中间件
app.use(fileUpload({
    createParentPath: true,
    limits: { 
        fileSize: 50 * 1024 * 1024  // 限制文件大小为 50MB
    },
}));

// 初始化数据库
sequelize.sync().then(() => {
    checkConnection().then()
})

// 设置静态文件目录
app.use('/assets', express.static(path.join(__dirname, 'assets')));

app.get('/', (req, res) => {
    res.status(200).send({
        "message": {"Server": "Running"}
    });
});

app.use('/celldata', cellDataRouter);
app.use('/nds', ndsRouter);
app.use('/node', nodeRouter);


// 启动服务器
const PORT = process.env.SERVER_PORT || 3000;
app.listen(PORT, () => {
    console.log(`服务启动, 端口:${PORT}`);
});
