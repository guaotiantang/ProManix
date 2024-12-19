const {DataTypes} = require('sequelize');

const sequelize = require('../../Libs/DataBasePool').sequelize;


const User = sequelize.define('User', {
    ID: {
        type: DataTypes.INTEGER,
        primaryKey: true,
        autoIncrement: true,
    },
    UserName: {
        type: DataTypes.STRING,
        allowNull: false,
    },
    Password: {
        type: DataTypes.STRING,
        allowNull: false,
    },
    Email: {
        type: DataTypes.STRING,
        allowNull: false,
    },
    Avatar: {
        type: DataTypes.STRING,
        allowNull: true,
        defaultValue: '/assets/images/avatars/default.svg',
    },
    CreateTime: {
        type: DataTypes.DATE,
        allowNull: false,
    },
    UpdateTime: {
        type: DataTypes.DATE,
        allowNull: false,
    },
}, {
    timestamps: false,
    tableName: 'User',
    freezeTableName: true,
    underscored: false,
    paranoid: true, // 软删除
    hooks: {
        beforeValidate: (user) => {
            user.CreateTime = new Date();
            user.UpdateTime = new Date();
        },
        beforeCreate(user) {
            user.CreateTime = new Date();
            user.UpdateTime = new Date();
        },
        beforeUpdate: (user) => {
            user.UpdateTime = new Date();
        }
    }
});

module.exports = { User };
