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
    },
    FileTime: {
        type: DataTypes.DATE,
        allowNull: false,
        field: 'FileTime'
    },
    DataType: {
        type: DataTypes.STRING(20),
        allowNull: false,
        field: 'DataType',
        comment: 'MDT/MRO'
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
        defaultValue: 0,
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
    tableName: 'NDSFileList',
    timestamps: false,
    hooks: {
        beforeValidate: (record) => {
            record.CreateTime = new Date();
            record.UpdateTime = new Date();
        },
        beforeCreate(record) {
            record.CreateTime = new Date();
            record.UpdateTime = new Date();
        },
        beforeUpdate: (record) => {
            record.UpdateTime = new Date();
        }
    },
    indexes: [
        {
            fields: ['ID'],
            name: 'ID'
        },
        {
            fields: ['NDSID'],
            name: 'NDSID'
        },
        {
            fields: ['FileTime'],
            name: 'FileTime'
        },
        {
            fields: ['DataType'],
            name: 'DataType'
        },
        {
            fields: ['eNodeBID'],
            name: 'eNodeBID'
        },
        {
            fields: ['NDSID', 'FilePath'],
            name: 'NDSID_FilePath'
        },
        {
            fields: ['eNodeBID', 'DataType'],
            name: 'eNodeBID_DataType'
        },
        {
            fields: ['eNodeBID', 'FileTime'],
            name: 'eNodeBID_FileTime'
        },
        {
            fields: ['eNodeBID', 'DataType', 'FileTime'],
            name: 'eNodeBID_DataType_FileTime'
        }
    ]
});

// 定义外键关系
NDSFileList.belongsTo(NDSList, {
    foreignKey: 'NDSID',
    onDelete: 'CASCADE',
    onUpdate: 'RESTRICT',
    constraints: true
});

module.exports = NDSFileList; 