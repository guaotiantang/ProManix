// noinspection JSCheckFunctionSignatures

require('crypto');
const jwt = require('jsonwebtoken');
const { RefreshToken } = require('../Models/Sys/RefreshToken');
const {hashToken, generateRefreshToken} = require("./Utils"); // 替换为您实际的模型路径


async function authMiddleware(req, res, next) {
    try {
        // 获取需要访问的URL
        const url = req.originalUrl;
        res.userId = null;
        // 从 Cookies 中获取 Access Token 和 Refresh Token
        const { accessToken, refreshToken } = req.cookies;
        if (!accessToken && !refreshToken) {
            // 没有 Token，无法验证用户身份
            return res.status(401).json({ message: '未授权访问，请先登录' });
        }

        let payload;
        try {
            // 验证 Access Token 是否有效
            payload = jwt.verify(accessToken, process.env.JWT_SECRET);
        } catch (error) {
            // Access Token 已过期或无效
            // 尝试使用 Refresh Token 来刷新 Access Token
            if (!refreshToken) {
                // 删除Cookies
                res.clearCookie('accessToken');
                return res.status(401).json({ message: '令牌已过期，请重新登录' });
            }

            // 查询数据库中的 Refresh Token 记录
            const tokenHash = hashToken(refreshToken);
            const tokenRecord = await RefreshToken.findOne({ where: { token_hash: tokenHash } });

            // 验证 Refresh Token 是否有效
            if (!tokenRecord || tokenRecord.revoked || new Date() > tokenRecord.expires_at) {
                // Refresh Token 无效或已过期
                // 删除Cookies
                res.clearCookie('accessToken');
                res.clearCookie('refreshToken');
                return res.status(401).json({ message: '刷新令牌无效或已过期，请重新登录' });
            }

            // 使用 Refresh Token 来生成新的 Access Token 和 Refresh Token
            // 撤销旧的 Refresh Token
            tokenRecord.revoked = true;
            await tokenRecord.save();

            // 为用户生成新的令牌
            const newAccessToken = jwt.sign({ UID: tokenRecord.user_id }, process.env.JWT_SECRET, { expiresIn: '15m' });
            const newRefreshToken = generateRefreshToken();
            const newTokenHash = hashToken(newRefreshToken);
            const newExpiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000); // 7天

            // 将新的 Refresh Token 存入数据库
            await RefreshToken.create({
                token_hash: newTokenHash,
                user_id: tokenRecord.user_id,
                expires_at: newExpiresAt,
            });

            // 设置新的令牌到 Cookies 中
            res.cookie('accessToken', newAccessToken, {
                httpOnly: true,
                secure: false,
                maxAge: 15 * 60 * 1000, // 15分钟
                sameSite: 'strict',
            });
            res.cookie('refreshToken', newRefreshToken, {
                httpOnly: true,
                secure: false,
                maxAge: 7 * 24 * 60 * 60 * 1000, // 7天
                sameSite: 'strict',
            });

            // 使用新的 Access Token 的payload
            payload = jwt.verify(newAccessToken, process.env.JWT_SECRET);
        }

        // 将用户ID信息附加到请求对象上，以便后续中间件或路由处理程序使用
        req.userId = payload.UID;

        next();
    } catch (error) {
        console.error('认证中间件出错:', error.message);
        return res.status(500).json({ message: '服务器错误，请稍后再试' });
    }
}

module.exports = { authMiddleware };
