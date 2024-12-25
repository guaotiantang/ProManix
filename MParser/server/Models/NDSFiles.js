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
            CREATE OR REPLACE VIEW NDSFiles AS 
            SELECT DISTINCT NDSID, FilePath 
            FROM NDSFileList
        `);
        console.log('View NDSFiles created successfully');
    } catch (error) {
        console.error('Error creating view:', error);
    }
}

// 在应用启动时创建视图
createView().catch(console.error);

module.exports = NDSFiles; 