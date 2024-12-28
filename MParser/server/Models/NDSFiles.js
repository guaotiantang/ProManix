// NDS文件清单视图，用于判断文件是否扫描过了

const { DataTypes } = require('sequelize');
const sequelize = require('../Libs/DataBasePool').sequelize;
const NDSList = require('./NDSList');

// 定义视图模型
const NDSFiles = sequelize.define('NDSFiles', {
    NDSID: {
        type: DataTypes.INTEGER,
        allowNull: false,
        field: 'NDSID',
        references: {
            model: NDSList,
            key: 'ID'
        }
    },
    FilePath: {
        type: DataTypes.STRING(250),
        allowNull: false,
        field: 'FilePath'
    }
}, {
    tableName: 'NDSFiles',
    timestamps: false,
    schema: null,
});

// 创建视图
async function createView() {
    try {
        await sequelize.query(`
            DROP TABLE IF EXISTS \`NDSFiles\`
        `);
        await sequelize.query(`
            CREATE OR REPLACE VIEW \`NDSFiles\` AS 
            SELECT DISTINCT NDSID, FilePath 
            FROM NDSFileList
        `);
    } catch (error) {
        console.error('Error creating view:', error);
        throw error;
    }
}

module.exports = {
    model: NDSFiles,
    createView
}; 