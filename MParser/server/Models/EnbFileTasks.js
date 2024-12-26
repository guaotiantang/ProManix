const { DataTypes } = require('sequelize');
const sequelize = require('../Libs/DataBasePool').sequelize;

// 定义视图模型
const EnbFileTasks = sequelize.define('EnbFileTasks', {
    // 从 NDSFileList 复制所有字段定义
    FileHash: {
        type: DataTypes.STRING(32),
        primaryKey: true,
        allowNull: false,
        field: 'FileHash'
    },
    NDSID: {
        type: DataTypes.INTEGER,
        allowNull: false,
        field: 'NDSID'
    },
    FilePath: {
        type: DataTypes.STRING(250),
        allowNull: false,
        field: 'FilePath'
    },
    FileTime: {
        type: DataTypes.DATE,
        allowNull: false,
        field: 'FileTime'
    },
    DataType: {
        type: DataTypes.STRING(20),
        allowNull: false,
        field: 'DataType'
    },
    eNodeBID: {
        type: DataTypes.INTEGER,
        allowNull: false,
        field: 'eNodeBID'
    },
    SubFileName: {
        type: DataTypes.STRING(250),
        allowNull: false,
        field: 'SubFileName'
    },
    HeaderOffset: {
        type: DataTypes.BIGINT,
        allowNull: false,
        field: 'HeaderOffset'
    },
    CompressSize: {
        type: DataTypes.BIGINT,
        allowNull: false,
        field: 'CompressSize'
    },
    FileSize: {
        type: DataTypes.BIGINT,
        allowNull: true,
        field: 'FileSize'
    },
    FlagBits: {
        type: DataTypes.INTEGER,
        allowNull: true,
        field: 'FlagBits'
    },
    CompressType: {
        type: DataTypes.INTEGER,
        allowNull: true,
        field: 'CompressType'
    },
    Parsed: {
        type: DataTypes.INTEGER,
        allowNull: false,
        field: 'Parsed'
    },
    CreateTime: {
        type: DataTypes.DATE,
        allowNull: false,
        field: 'CreateTime'
    },
    UpdateTime: {
        type: DataTypes.DATE,
        allowNull: false,
        field: 'UpdateTime'
    }
}, {
    tableName: 'EnbFileTasks',
    timestamps: false,
    schema: null,
});

// 创建视图
async function createView() {
    try {
        await sequelize.query(`
            CREATE OR REPLACE VIEW EnbFileTasks AS 
            SELECT DISTINCT 
                NDSFileList.* 
            FROM NDSFileList 
            INNER JOIN EnbTaskList 
                ON NDSFileList.Parsed = 0 
                AND NDSFileList.eNodeBID = EnbTaskList.eNodeBID 
                AND NDSFileList.DataType = EnbTaskList.DataType 
                AND NDSFileList.FileTime BETWEEN EnbTaskList.StartTime AND EnbTaskList.EndTime 
            ORDER BY NDSFileList.FileTime
        `);
    } catch (error) {
        console.error('Error creating view:', error);
    }
}

// 在应用启动时创建视图
createView().catch(console.error);

module.exports = EnbFileTasks; 