// noinspection JSCheckFunctionSignatures

const bcrypt = require('bcrypt');
const express = require('express');
const jwt = require('jsonwebtoken');
require('crypto');
const { User }  = require('../../Models/Sys/User.js');
const { RefreshToken } = require('../../Models/Sys/RefreshToken');
const { decryptPassword, BCRYPT_SALT_ROUNDS, regExp, loginExp, generateRefreshToken, hashToken} = require("../../Libs/Utils");
const {authMiddleware} = require("../../Libs/middleware");
const router = express.Router();
const path = require('path');
const fs = require('fs');



// 注册
router.post('/register', async (req, res) => {
    const ip = req.headers['x-forwarded-for'] || req.ip || req.socket.remoteAddress;
    if (regExp.getCount(ip) > process.env.REGISTRATION_LIMIT) {
        return res.status(429).json({ message: '注册过于频繁，请24小时后再试' });
    } else {
        regExp.addCount(ip);
    }
    const { Email, UserName, Password, iv } = req.body;

    try {
        const decryptedPassword = decryptPassword(Password, iv);
        const validations = [
            { valid: decryptedPassword.length < 6, message: '密码过短', status: 422 },
            { valid: UserName.length < 2, message: '用户名过短', status: 422 },
            { valid: await User.findOne({ where: { Email } }), message: '该邮箱已被注册账号', status: 409 },
        ];
        for (const validation of validations) {
            if (validation.valid) {
                return res.status(validation.status).json({ message: validation.message });
            }
        }
        const hashedPassword = await bcrypt.hash(decryptedPassword, BCRYPT_SALT_ROUNDS);
        await User.create({
            Email,
            UserName,
            Password: hashedPassword,
            UserGroupID: -1,
        });
        res.status(200).json({ data: '用户注册成功' });
    } catch (error) {
        res.status(500).json({ message: `服务器错误: ${error.message}` });
        console.error(error.message);
    }
});

// 登录
router.post('/login', async (req, res) => {
    const { Email, Password, iv } = req.body;
    if (!Email || !Password) {
        return res.status(422).json({ message: '邮箱或密码不能为空' });
    }
    try {
        const decryptedPassword = decryptPassword(Password, iv);
        const user = await User.findOne({ where: { Email } });
        if (!user) {
            return res.status(401).json({ message: '账号不存在' });
        }

        const pwdFailCount = loginExp.getCount(user.ID);
        if (pwdFailCount > process.env.LOGIN_LIMIT) {
            return res.status(429).json({ message: '登录失败次数过多，请稍后再试' });
        }

        if (decryptedPassword.length <= 3 || !(await bcrypt.compare(decryptedPassword, user.Password))) {
            loginExp.addCount(user.ID);
            return res.status(401).json({ message: '密码错误!' });
        }

        // 登录成功，重置密码错误次数
        loginExp.resetCount(user.ID);

        // 生成 Access Token
        const accessToken = jwt.sign({ UID: user.ID }, process.env.JWT_SECRET, { expiresIn: '15m' });

        // 生成 Refresh Token
        const refreshToken = generateRefreshToken();
        const tokenHash = hashToken(refreshToken);
        const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000); // 7天后过期

        // 将 Refresh Token 存储到数据库
        await RefreshToken.create({
            token_hash: tokenHash,
            user_id: user.ID,
            expires_at: expiresAt,
        });

        // 设置 Access Token 和 Refresh Token 到 cookies 中
        res.cookie('accessToken', accessToken, {
            httpOnly: true,
            secure: false, // HTTPS环境下设为 true
            maxAge: 15 * 60 * 1000, // 15分钟
            sameSite: 'strict',
        });

        res.cookie('refreshToken', refreshToken, {
            httpOnly: true,
            secure: false,
            maxAge: 7 * 24 * 60 * 60 * 1000, // 7天
            sameSite: 'strict',
        });

        res.status(200).json({ data: '登录成功' });
    } catch (error) {
        res.status(500).json({ message: `服务器错误: ${error.message}` });
        console.error(error.message);
    }
});

// 注销
router.get('/logout', async (req, res) => {
    const { refreshToken } = req.cookies;
    if (refreshToken) {
        const tokenHash = hashToken(refreshToken);
        await RefreshToken.destroy({ where: { token_hash: tokenHash } });
    }
    res.clearCookie('accessToken');
    res.clearCookie('refreshToken');
    res.status(200).json({ message: '注销成功' });
});


router.get('/info', authMiddleware, async (req, res) => {
    if (!req.userId) {
        res.clearCookie('accessToken');
        res.clearCookie('refreshToken');
        return res.status(401).json({ message: '令牌已过期，请重新登录' });
    }
    const user = req.userId? await User.findOne({ where: { ID: req.userId } }) : null;
    if (!user) {
        return res.status(403).json({ message: '用户不存在' });
    }

    res.status(200).json({
        ID: user.ID,
        Email: user.Email,
        UserName: user.UserName,
        Avatar: user.Avatar,
        CreateTime: user.CreateTime.toISOString().replace('T', ' ').substring(0, 19),
    });
});


// 修改用户信息
router.put('/update', authMiddleware, async (req, res) => {
    const { Email, UserName, Password, iv } = req.body;
    const user = await User.findOne({ where: { ID: req.userId } });
    if (!user) {
        return res.status(403).json({ message: '用户不存在' });
    }
    try {
        await user.update({
            Email: Email || user.Email,
            UserName: UserName || user.UserName,
            Password: Password && iv ? await bcrypt.hash(decryptPassword(Password, iv), BCRYPT_SALT_ROUNDS) : user.Password
        });
        res.status(200).json({ message: '用户信息修改成功' });
    } catch (error) {
        res.status(500).json({ message: `服务器错误: ${error.message}` });
        console.error(error.message);
    }
});

// 修改头像接口
router.put('/update/avatar', authMiddleware, async (req, res) => {
    try {
        const { Avatar } = req.body;
        if (!Avatar) {
            return res.status(400).json({ message: '请选择要上传的图片' });
        }

        const user = await User.findOne({ where: { ID: req.userId } });
        if (!user) {
            return res.status(403).json({ message: '用户不存在' });
        }

        // 将base64转换为图片文件
        const buffer = Buffer.from(Avatar, 'base64');
        
        // 确保目录存在
        const uploadPath = 'assets/images/avatars';
        if (!fs.existsSync(uploadPath)) {
            fs.mkdirSync(uploadPath, { recursive: true });
        }

        // 生成文件名
        const fileName = `${req.userId}_${Date.now()}.jpg`;
        const filePath = path.join(uploadPath, fileName);
        
        // 如果存在旧头像，删除它
        if (user.Avatar && user.Avatar != '/assets/images/avatars/default.svg' && fs.existsSync('.' + user.Avatar)) {
            fs.unlinkSync('.' + user.Avatar);
        }

        // 写入新文件
        fs.writeFileSync(filePath, buffer);
        
        const avatarPath = `/assets/images/avatars/${fileName}`;
        await user.update({ Avatar: avatarPath });

        res.status(200).json({ 
            message: '头像修改成功',
            avatarUrl: avatarPath
        });
    } catch (error) {
        res.status(500).json({ message: `服务器错误: ${error.message}` });
        console.error(error.message);
    }
});


module.exports = router;
