const { DataTypes } = require('sequelize');
const sequelize = require('../Libs/DataBasePool').sequelize;

const NodeList = sequelize.define('NodeList', {
    ID: {
        type: DataTypes.BIGINT,
        primaryKey: true,
        autoIncrement: true,
        field: 'ID'
    },
    NodeType: {
        type: DataTypes.STRING(128),
        allowNull: true,
        field: 'NodeType'
    },
    NodeName: {
        type: DataTypes.STRING(128),
        allowNull: true,
        field: 'NodeName'
    },
    Host: {
        type: DataTypes.STRING(128),
        allowNull: true,
        field: 'Host'
    },
    Port: {
        type: DataTypes.INTEGER,
        allowNull: true,
        field: 'Port'
    },
    Status: {
        type: DataTypes.STRING(128),
        allowNull: true,
        field: 'Status'
    },
    CreateTime: {
        type: DataTypes.DATE,
        allowNull: true,
        field: 'CreateTime'
    }
}, {
    tableName: 'NodeList',
    timestamps: false,
    indexes: [
        {
            fields: ['NodeType']
        },
        {
            fields: ['NodeName']
        },
        {
            fields: ['Host']
        },
        {
            fields: ['Port']
        }
    ],
    hooks: {
        beforeValidate: (record) => {
            record.CreateTime = new Date();
        },
        beforeCreate(record) {
            record.CreateTime = new Date();
        }
    }
});

module.exports = NodeList; 