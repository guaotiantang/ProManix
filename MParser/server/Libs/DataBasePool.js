const { Sequelize } = require('sequelize');

const sequelize = new Sequelize(
    process.env.DB_NAME,
    process.env.DB_USER,
    process.env.DB_PASSWORD,
    {
        host: process.env.DB_HOST,
        port: process.env.DB_PORT || 3306,
        dialect: 'mysql',
        logging: false, // 禁用日志输出
        pool: { //连接池配置
            max: 500,        // 连接池最大连接数
            min: 5,         // 最小连接数
            acquire: 60000, // 获取连接的超时时间
            idle: 10000,    // 连接空闲时间
        },
        dialectOptions: {
            connectTimeout: 60000,  // 增加连接超时
            // 其他 MySQL 特定选项
            supportBigNumbers: true,
            bigNumberStrings: true
        },
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

module.exports = { sequelize, Sequelize, checkConnection };
