const { DataTypes, Sequelize } = require('sequelize');
const sequelize = require('../../Libs/DataBasePool').sequelize;

const RefreshToken = sequelize.define('RefreshToken', {
    id: {
        type: DataTypes.INTEGER,
        primaryKey: true,
        autoIncrement: true,
    },
    token_hash: {
        type: DataTypes.CHAR(64), // SHA-256 哈希值
        allowNull: false,
        unique: true,
    },
    user_id: {
        type: DataTypes.INTEGER,
        allowNull: false,
    },
    expires_at: {
        type: DataTypes.DATE,
        allowNull: false,
    },
    revoked: {
        type: DataTypes.BOOLEAN,
        allowNull: false,
        defaultValue: false,
    },
    created_at: {
        type: DataTypes.DATE,
        allowNull: false,
        defaultValue: Sequelize.literal('CURRENT_TIMESTAMP'),
    },
}, {
    timestamps: false,
    tableName: 'RefreshToken',
    freezeTableName: true,
    underscored: false,
    paranoid: false,
    engine: 'MEMORY', // 指定存储引擎为 MEMORY
    hooks: {
        beforeValidate(token) {
            token.created_at = new Date();
        },
        beforeCreate: (token) => {
            token.created_at = new Date();
        },

    },
    indexes: [
        {
            name: 'idx_user_id',
            fields: ['user_id'],
        },
        {
            name: 'idx_expires_at',
            fields: ['expires_at'],
        },
    ],
});

module.exports = { RefreshToken };
