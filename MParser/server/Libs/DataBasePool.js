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
            min: 50, // 连接池最小连接数
            acquire: 30000, // 连接池获取连接的最大等待时间，单位毫秒
            idle: 10000 // 连接池中连接的空闲时间，单位毫秒
        },
        timezone: '+08:00',  // 设置时区为 UTC+8
        dialectOptions: {
            // 确保从数据库读取的时间也是正确的时区
            dateStrings: true,
            typeCast: true
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
