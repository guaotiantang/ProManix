const { DataTypes } = require('sequelize');
const sequelize = require('../Libs/DataBasePool').sequelize;
const NDSList = require('./NDSList');

const NDSFileList = sequelize.define('NDSFileList', {
    ID: {
        type: DataTypes.BIGINT,
        primaryKey: true,
        autoIncrement: true,
        field: 'ID'
    },
    NDSID: {
        type: DataTypes.INTEGER,
        allowNull: true,
        field: 'NDSID',
        references: {
            model: NDSList,
            key: 'ID'
        }
    },
    DataType: {
        type: DataTypes.STRING(20),
        allowNull: false,
        field: 'DataType',
        comment: 'MDT/MRO'
    },
    FilePath: {
        type: DataTypes.STRING(250),
        allowNull: true,
        field: 'FilePath'
    },
    FileTime: {
        type: DataTypes.DATE,
        allowNull: false,
        field: 'FileTime'
    },
    Parsed: {
        type: DataTypes.INTEGER,
        allowNull: true,
        defaultValue: 0,
        field: 'Parsed'
    },
    AddTime: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: DataTypes.NOW,
        field: 'AddTime'
    }
}, {
    tableName: 'NDSFileList',
    timestamps: false,
    indexes: [
        {
            unique: true,
            fields: ['NDSID', 'FilePath'],
            name: 'NDSFile'
        },
        {
            fields: ['ID']
        },
        {
            fields: ['Parsed']
        },
        {
            fields: ['NDSID', 'DataType', 'FilePath']
        }
    ]
});

// 定义外键关系
NDSFileList.belongsTo(NDSList, {
    foreignKey: 'NDSID',
    onDelete: 'CASCADE',
    onUpdate: 'RESTRICT'
});

module.exports = NDSFileList; 