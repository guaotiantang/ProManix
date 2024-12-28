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

// 添加数据库初始化函数
async function initDatabase() {
    try {
        // 1. 检查数据库连接
        await sequelize.authenticate();
        console.log('数据库连接成功');

        // 2. 导入所有模型（按依赖顺序）
        const models = {
            NodeList: require('../Models/NodeList'),
            NDSList: require('../Models/NDSList'),
            NDSFileList: require('../Models/NDSFileList'),
            CellData: require('../Models/CellData'),
            EnbTaskList: require('../Models/EnbTaskList')
        };

        // 3. 同步所有基础表
        for (const [name, model] of Object.entries(models)) {
            try {
                await model.sync({ force: false });
            } catch (error) {
                console.error(`表 ${name} 同步失败:`, error.message);
                throw error;
            }
        }

        // 4. 确认所有表都已创建
        const [tables] = await sequelize.query(
            `SELECT TABLE_NAME FROM information_schema.TABLES 
             WHERE TABLE_SCHEMA = '${process.env.DB_NAME}'
             AND TABLE_TYPE = 'BASE TABLE'`
        );
        
        const existingTables = tables.map(t => t.TABLE_NAME.toLowerCase());
        const requiredTables = Object.values(models).map(model => model.tableName.toLowerCase());
        
        const missingTables = requiredTables.filter(table => !existingTables.includes(table));
        if (missingTables.length > 0) {
            throw new Error(`缺少必需的表: ${missingTables.join(', ')}`);
        }

        // 5. 创建视图
        const { createView: createNDSFilesView } = require('../Models/NDSFiles');
        const { createView: createEnbFileTasksView } = require('../Models/EnbFileTasks');

        try {
            await createNDSFilesView();
        } catch (error) {
            console.warn('NDSFiles 视图创建警告:', error.message);
        }

        try {
            await createEnbFileTasksView();
        } catch (error) {
            console.warn('EnbFileTasks 视图创建警告:', error.message);
        }

        console.log('数据库初始化完成');
        return true;
    } catch (error) {
        console.error('数据库初始化失败:', error);
        throw error;
    }
}

module.exports = {
    sequelize,
    Sequelize,
    initDatabase
};
