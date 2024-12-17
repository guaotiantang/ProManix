const { Sequelize} = require('sequelize');

const sequelize = new Sequelize(
    // 使用环境变量配置数据库连接
    process.env.DB_NAME,
    process.env.DB_USER,
    process.env.DB_PASSWORD,
    {
        host: process.env.DB_HOST,
        dialect: 'mysql',
        logging: false, // 禁用日志输出
        pool: { //连接池配置
            max: 5000, // 连接池最大连接数
            min: 10, // 连接池最小连接数
            acquire: 30000, // 连接池获取连接的最大等待时间，单位毫秒
            idle: 10000 // 连接池中连接的空闲时间，单位毫秒
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
