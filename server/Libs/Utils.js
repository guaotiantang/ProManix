
// noinspection JSUnresolvedReference

const CryptoJS = require("crypto-js");
const crypto = require('crypto');
const BCRYPT_SALT_ROUNDS = parseInt(process.env.BCRYPT_SALT_ROUNDS, 10);
const SECRET_KEY = process.env.SECRET_KEY; // AES 密钥
if (!SECRET_KEY) {
    console.error('SECRET_KEY is not defined!');
    process.exit(1); // 如果未定义，停止程序并提示错误
}
// AES 解密函数
function decryptPassword(encryptedPassword, iv) {
    const decrypted = CryptoJS["AES"].decrypt(encryptedPassword, CryptoJS["enc"].Hex.parse(SECRET_KEY), {
        iv: CryptoJS["enc"].Hex.parse(iv),
        mode: CryptoJS["mode"].CBC,
        padding: CryptoJS["pad"].Pkcs7,
    });
    // 将解密后的数据转换为 UTF-8 字符串
    return decrypted.toString();
}

// 内存存储模块 用户量大可考虑使用数据库
// 限制注册次数
const regLimit = new Map();
const regExp = {
    lastCleanTime: Date.now(), // 上次清理的时间
    addCount(ip) {
        this.clean(); // 进行清理操作

        let reg = regLimit.get(ip) || { count: 0, lastUpdate: Date.now() };
        // 判断时间是否超过24小时，如果是则清零
        reg.count = Date.now() - reg.lastUpdate > 86400000 ? 0 : reg.count;
        regLimit.set(ip, { count: reg.count + 1, lastUpdate: Date.now() });
    },
    getCount(ip) {
        this.clean(); // 进行清理操作
        let reg = regLimit.get(ip) || { count: 0, lastUpdate: Date.now() };
        reg.count = Date.now() - reg.lastUpdate > 86400000 ? 0 : reg.count;
        return reg.count;
    },
    clean() {
        const now = Date.now();
        // 如果距离上次清理超过8小时，则执行清理
        if (now - this.lastCleanTime > 8 * 60 * 60 * 1000) {
            for (let [ip, data] of regLimit.entries()) {
                // 删除那些超过24小时没有更新的数据
                if (now - data.lastUpdate > 86400000) {
                    regLimit.delete(ip);
                }
            }
            this.lastCleanTime = now; // 更新上次清理的时间
        }
    }
};

// 限制登录次数
const loginLimit = new Map();
const loginExp = {
    lastCleanTime: Date.now(), // 上次清理的时间
    addCount(UID) {
        this.clean(); // 进行清理操作
        let login = loginLimit.get(UID) || { count: 0, lastUpdate: Date.now() };
        // 判断时间是否超过24小时，如果是则清零
        login.count = Date.now() - login.lastUpdate > 86400000 ? 0 : login.count;
        loginLimit.set(UID, { count: login.count + 1, lastUpdate: Date.now() });
    },
    getCount(UID) {
        this.clean(); // 进行清理操作
        let login = loginLimit.get(UID) || { count: 0, lastUpdate: Date.now() };
        login.count = Date.now() - login.lastUpdate > 86400000 ? 0 : login.count;
        return login.count;
    },
    clean() {
        const now = Date.now();
        // 如果距离上次清理超过8小时，则执行清理
        if (now - this.lastCleanTime > 8 * 60 * 60 * 1000)
            for (let [UID, data] of loginLimit.entries())
                // 删除那些超过24小时没有更新的数据
                if (now - data.lastUpdate > 86400000)
                    loginLimit.delete(UID);
        this.lastCleanTime = now; // 更新上次清理的时间
    },
    resetCount(UID) {
        loginLimit.set(UID, { count: 0, lastUpdate: Date.now() });
    }
};

// 辅助函数：哈希 Refresh Token
function hashToken(token) {
    return crypto.createHash('sha256').update(token).digest('hex');
}

// 辅助函数：生成随机 Refresh Token
function generateRefreshToken() {
    return crypto.randomBytes(64).toString('hex'); // 128字符的十六进制字符串
}

module.exports = {
    BCRYPT_SALT_ROUNDS,
    decryptPassword,
    regExp,
    loginExp,
    hashToken,
    generateRefreshToken
};
