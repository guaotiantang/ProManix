const {DataTypes} = require('sequelize');
const sequelize = require('../Libs/DataBasePool').sequelize;

const CellData = sequelize.define('CellData', {
    CGI: {
        type: DataTypes.STRING(128),
        allowNull: true,
        unique: true,
        primaryKey: true,
        field: 'CGI'
    },
    eNodeBID: {
        type: DataTypes.INTEGER,
        allowNull: true,
        field: 'eNodeBID'
    },
    PCI: {
        type: DataTypes.INTEGER,
        allowNull: true,
        field: 'PCI'
    },
    Azimuth: {
        type: DataTypes.INTEGER,
        allowNull: true,
        field: 'Azimuth'
    },
    Earfcn: {
        type: DataTypes.INTEGER,
        allowNull: true,
        field: 'Earfcn'
    },
    Freq: {
        type: DataTypes.DOUBLE,
        allowNull: true,
        field: 'Freq'
    },
    eNBName: {
        type: DataTypes.STRING(200),
        allowNull: true,
        field: 'eNBName'
    },
    userLabel: {
        type: DataTypes.STRING(200),
        allowNull: true,
        field: 'userLabel'
    },
    Longitude: {
        type: DataTypes.DOUBLE,
        allowNull: true,
        field: 'Longitude'
    },
    Latitude: {
        type: DataTypes.DOUBLE,
        allowNull: true,
        field: 'Latitude'
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
    },
}, {
    tableName: 'CellData',
    timestamps: false, // 不使用时间戳字段
    indexes: [
        {
            fields: ['eNodeBID']
        },
        {
            fields: ['PCI']
        },
        {
            fields: ['Earfcn']
        },
        {
            fields: ['Freq']
        }
    ],
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
    }
});

module.exports = CellData;
