const sequelize = require('../Libs/DataBasePool').sequelize;
const {DataTypes} = require('sequelize');

const EnbTaskList = sequelize.define('EnbTaskList', {
    ID: {
        type: DataTypes.INTEGER,
        primaryKey: true,
        autoIncrement: true,
        allowNull: false,
        field: 'ID'
    },
    TaskID: {
        type: DataTypes.INTEGER,
        allowNull: false,
        field: 'TaskID'
    },
    eNodeBID: {
        type: DataTypes.INTEGER,
        allowNull: false,
        field: 'eNodeBID'
    },
    DataType: {
        type: DataTypes.STRING(20),
        allowNull: false,
        field: 'DataType'
    },
    StartTime: {
        type: DataTypes.DATE,
        allowNull: false,
        field: 'StartTime'
    },
    EndTime: {
        type: DataTypes.DATE,
        allowNull: false,
        field: 'EndTime'
    }
}, {
    tableName: 'EnbTaskList',
    timestamps: false,
    indexes: [
        {
            fields: ['TaskID'],
            name: 'TaskID'
        },
        {
            fields: ['eNodeBID', 'DataType', 'StartTime', 'EndTime'],
            name: 'TaskIndex'
        }
    ]
});

module.exports = EnbTaskList; 