process.noDeprecation = true; // 禁用弃用警告
require('dotenv').config(); // 加载 .env 文件中的配置
const path = require('path');

// 引入HTTP接口依赖
const express = require('express');
const cors = require('cors');
const cookieParser = require('cookie-parser');

// 引入数据库依赖
const {sequelize, checkConnection} = require("./Libs/DataBasePool");


// 引入中间件
const {authMiddleware} = require("./Libs/middleware");
const {createProxyMiddleware} = require('http-proxy-middleware');


const app = express();
app.use(cookieParser()); //启用Cookies插件
app.use(cors({
    origin: '*',
    credentials: true,
}));

// 初始化数据库
sequelize.sync().then(() => {
    checkConnection().then()
})


// 添加错误处理中间件来捕获解析错误
app.use((err, res, next) => {
    if (err instanceof SyntaxError && err.status === 400 && 'body' in err) {
        return res.status(400).send({ message: '请求体格式错误' });
    }
    next();
});

// 代理中间件配置
const httpProxyConfigs = [
    {url: "http://localhost:9002", route: "/mparser", pathRewrite: {}, useAuth: true}
];

// 创建通用的代理配置
const createProxyConfig = (config) => ({
    target: config.url,
    pathRewrite: config.pathRewrite,
    changeOrigin: true,
    ws: true
});

// 设置代理路由
for (const config of httpProxyConfigs) {
    const middlewares = [createProxyMiddleware(createProxyConfig(config))];
    if (config.useAuth) middlewares.unshift(authMiddleware);
    app.use(config.route, ...middlewares);
}



// 设置body解析器, body-parser必须放在proxyMiddleware之后, 否则无法代理post请求
// 设置请求体大小限制
app.use(express.json({limit: '50mb'}));
app.use(express.urlencoded({limit: '50mb', extended: true}));


// 设置静态文件目录
app.use('/assets', express.static(path.join(__dirname, 'assets')));
app.use('/user', require('./APIs/Sys/User'));

app.get('/', (req, res) => {
    res.status(200).send({
        "message": {
            "server": "online",
            "accessToken": req.cookies.accessToken || null,
            "refreshToken": req.cookies.refreshToken || null,
        }
    });
});






// 启动服务器
const PORT = process.env.SERVER_PORT || 3000;
app.listen(PORT, () => {
    console.log(`服务启动, 端口:${PORT}`);
});

