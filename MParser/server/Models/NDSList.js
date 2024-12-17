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
    AddTime: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: DataTypes.NOW,
        field: 'AddTime'
    }
}, {
    tableName: 'NDSList',
    timestamps: false
});

module.exports = NDSList;
