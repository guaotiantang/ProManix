const { Server } = require('socket.io');
const axios = require('axios');
const express = require('express');
const router = express.Router();

// 定义日志级别
const LogLevel = {
    ERROR: 0,   // 只输出错误
    WARN: 1,    // 输出警告和错误
    INFO: 2,    // 输出一般信息、警告和错误
    DEBUG: 3    // 输出所有信息
};

class ApiHandler {
    constructor() { this.apiHandlers = new Map(); } // API处理器映射

    // 注册API处理器
    register(api, handler) {
        if (typeof handler !== 'function') {
            throw new Error(`处理器必须是函数: ${api}`);
        }
        this.apiHandlers.set(api, handler);
        return this;  // 支持链式调用
    }

    // 批量注册API处理器
    registerBatch(handlers) {
        for (const [api, handler] of Object.entries(handlers)) {
            this.register(api, handler);
        }
        return this;
    }

    // 处理API请求
    async handleRequest(api, data) {
        const handler = this.apiHandlers.get(api);
        if (!handler) {
            throw new Error(`未知的API: ${api}`);
        }
        return await handler(data);
    }
}

class SocketServer {
    constructor(httpServer, options = {}) {
        this.logLevel = options.logLevel || LogLevel.INFO;  // 默认 INFO 级别
        
        // 初始化API处理器
        this.apiHandler = new ApiHandler();

        // Socket.IO配置
        this.io = new Server(httpServer, {
            cors: {
                origin: options.corsOrigin || "*",
                methods: ["GET", "POST"]
            },
            pingTimeout: options.pingTimeout || 10000,  // 10秒没有响应就断开
            pingInterval: options.pingInterval || 5000,  // 每5秒发送一次心跳
            reconnectionAttempts: options.reconnectionAttempts || 2,  // 重连次数
            reconnectionDelay: options.reconnectionDelay || 1000  // 重连延迟(毫秒)
        });

        // 设置Socket处理器
        this.setupSocketHandlers();
        // 设置路由
        this.setupRouter();
    }

    log(level, message, error = null) {
        if (level <= this.logLevel) {
            switch(level) {
                case LogLevel.ERROR:
                    console.error(message, error || '');
                    break;
                case LogLevel.WARN:
                    console.warn(message);
                    break;
                case LogLevel.INFO:
                    console.log(message);
                    break;
                case LogLevel.DEBUG:
                    console.debug(message);
                    break;
            }
        }
    }

    // 注册API处理器
    registerHandler(api, handler) {
        this.apiHandler.register(api, handler);
        return this;
    }

    // 批量注册API处理器
    registerBatch(handlers) {
        for (const [api, handler] of Object.entries(handlers)) {
            this.apiHandler.register(api, handler);
        }
        return this;
    }

    // 设置HTTP路由
    setupRouter() {
        router.post('/call', async (req, res) => {
            const { api, data, callback_type, callback_url, callback_func, request_id } = req.body;
            
            this.log(LogLevel.DEBUG, `收到HTTP请求: ${api}`);
            res.json({
                success: true,
                message: '请求已接收',
                request_id
            });

            try {
                const response = await this.apiHandler.handleRequest(api, data);
                // 回调响应包含完整信息
                const result = {
                    request_id,
                    api,
                    success: true,
                    data: response,
                    message: '处理成功',
                    callback_func  // 在回调中返回 callback_func
                };

                if (callback_type === 'socket') {
                    try {
                        this.io.emit('apiResponse', result);
                        this.log(LogLevel.DEBUG, `Socket回调成功: ${api}`);
                    } catch (error) {
                        this.log(LogLevel.ERROR, `Socket回调失败: ${api}`, error);
                        if (callback_url) {
                            try {
                                await axios.post(callback_url, result);
                                this.log(LogLevel.INFO, `HTTP降级回调成功: ${api}`);
                            } catch (httpError) {
                                this.log(LogLevel.ERROR, '回调失败:', httpError);
                            }
                        } else {
                            this.log(LogLevel.ERROR, `Socket回调失败且未配置HTTP回调: ${api}`, error);
                        }
                    }
                } else if (callback_url) {
                    try {
                        await axios.post(callback_url, result);
                        this.log(LogLevel.DEBUG, `HTTP回调成功: ${api}`);
                    } catch (error) {
                        this.log(LogLevel.ERROR, `HTTP回调失败: ${api}`, error);
                    }
                } else {
                    this.log(LogLevel.WARN, `未配置回调地址: ${api}`);
                }
            } catch (error) {
                this.log(LogLevel.ERROR, `API处理失败: ${api}`, error);
                const errorResult = {
                    request_id,
                    api,
                    success: false,
                    error: error.message,
                    callback_func  // 错误回调也包含 callback_func
                };

                if (callback_type === 'socket') {
                    try {
                        this.io.emit('apiResponse', errorResult);
                    } catch (socketError) {
                        if (callback_url) {  // 只有设置了callback_url才尝试HTTP
                            try {
                                await axios.post(callback_url, errorResult);
                            } catch (httpError) {
                                console.error('回调失败:', httpError);
                            }
                        } else {
                            console.error('Socket回调失败且未配置HTTP回调:', socketError);
                        }
                    }
                } else if (callback_url) {  // HTTP模式且设置了callback_url
                    try {
                        await axios.post(callback_url, errorResult);
                    } catch (error) {
                        console.error('回调失败:', error);
                    }
                } else {
                    console.error('未配置回调地址');
                }
            }
        });
    }

    // 设置Socket处理器
    setupSocketHandlers() {
        this.io.on('connection', (socket) => {
            this.log(LogLevel.INFO, `客户端连接: ${socket.id}`);

            socket.on('api', async (request) => {
                this.log(LogLevel.DEBUG, `收到API请求: ${request.api}`);
                try {
                    const response = await this.apiHandler.handleRequest(request.api, request.data);
                    socket.emit('apiResponse', {
                        request_id: request.request_id,
                        api: request.api,
                        success: true,
                        data: response,
                        message: '处理成功',
                        callback_func: request.callback_func
                    });
                    this.log(LogLevel.DEBUG, `API处理成功: ${request.api}`);
                } catch (error) {
                    this.log(LogLevel.ERROR, `API处理失败: ${request.api}`, error);
                    socket.emit('apiResponse', {
                        request_id: request.request_id,
                        api: request.api,
                        success: false,
                        error: error.message,
                        callback_func: request.callback_func
                    });
                }
            });

            socket.on('disconnect', (reason) => {
                this.log(LogLevel.INFO, `客户端断开连接: ${socket.id}, 原因: ${reason}`);
            });

            socket.on('error', (error) => {
                this.log(LogLevel.ERROR, `socket错误: ${socket.id}`, error);
            });
        });
    }

    // 获取Express路由
    getRouter() {
        return router;
    }
}

module.exports = { SocketServer, LogLevel };