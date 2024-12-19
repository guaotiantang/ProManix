const { DataTypes } = require('sequelize');
const sequelize = require('../Libs/DataBasePool').sequelize;

const NDSGateways = sequelize.define('NDSGateways', {
    ID: {
        type: DataTypes.INTEGER,
        primaryKey: true,
        autoIncrement: true,
        field: 'ID'
    },
    Host: {
        type: DataTypes.STRING(128),
        allowNull: false,
        field: 'Host'
    },
    Port: {
        type: DataTypes.INTEGER,
        allowNull: false,
        field: 'Port'
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
    tableName: 'NDSGateways',
    timestamps: false,
    indexes: [
        {
            fields: ['ID']
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

module.exports = NDSGateways; 