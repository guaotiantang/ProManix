const {DataTypes} = require('sequelize');
const sequelize = require('../Libs/DataBasePool').sequelize;

const NDSList = sequelize.define('NDSList', {
    ID: {
        type: DataTypes.INTEGER,
        primaryKey: true,
        autoIncrement: true,
        field: 'ID'
    },
    NDSName: {
        type: DataTypes.STRING(150),
        allowNull: false,
        field: 'NDSName'
    },
    Address: {
        type: DataTypes.STRING(100),
        allowNull: false,
        field: 'Address'
    },
    Port: {
        type: DataTypes.INTEGER,
        allowNull: true,
        field: 'Port'
    },
    Protocol: {
        type: DataTypes.STRING(20),
        allowNull: false,
        field: 'Protocol'
    },
    Account: {
        type: DataTypes.STRING(100),
        allowNull: true,
        field: 'Account'
    },
    Password: {
        type: DataTypes.STRING(100),
        allowNull: true,
        field: 'Password'
    },
    MRO_Path: {
        type: DataTypes.STRING(250),
        allowNull: true,
        field: 'MRO_Path'
    },
    MRO_Filter: {
        type: DataTypes.STRING(250),
        allowNull: true,
        field: 'MRO_Filter'
    },
    MDT_Path: {
        type: DataTypes.STRING(250),
        allowNull: true,
        field: 'MDT_Path'
    },
    MDT_Filter: {
        type: DataTypes.STRING(250),
        allowNull: true,
        field: 'MDT_Filter'
    },
    Status: {
        type: DataTypes.INTEGER,
        allowNull: false,
        defaultValue: 1,
        field: 'Status'
    },
    Switch: {
        type: DataTypes.INTEGER,
        allowNull: false,
        defaultValue: 1,
        field: 'Switch'
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
    tableName: 'NDSList',
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
    }
});

module.exports = NDSList;
