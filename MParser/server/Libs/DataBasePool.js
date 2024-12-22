const { Sequelize } = require('sequelize');

const sequelize = new Sequelize(
    process.env.DB_NAME,
    process.env.DB_USER,
    process.env.DB_PASSWORD,
    {
        host: process.env.DB_HOST,
        dialect: 'mysql',
        logging: false, // 禁用日志输出
        pool: { //连接池配置
            max: 200,        // 连接池最大连接数
            min: 5,         // 最小连接数
            acquire: 60000, // 获取连接的超时时间
            idle: 10000,    // 连接空闲时间
            evict: 1000     // 清理空闲连接的频率
        },
        timezone: '+08:00',  // 设置时区为 UTC+8
        dialectOptions: {
            multipleStatements: true,
            dateStrings: true,
            typeCast: true
        },
        retry: {
            max: 3,         // 重试次数
            timeout: 30000  // 重试超时
        }
    }
);

async function checkConnection() {
    // 测试数据库连接
    try {
        await sequelize.authenticate();
        console.log('数据库初始化成功');
    } catch (error) {
        console.error('无法连接到数据库,服务启动失败', error.message);
        process.exit(1); // 退出程序
    }
}

module.exports = { sequelize, checkConnection };
