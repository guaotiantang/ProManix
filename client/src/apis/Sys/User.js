// noinspection JSUnresolvedReference

import CryptoJS from "crypto-js";
import { tabStore, userInfoStore, isLogin } from "@/store/index.js";
import {server, showMsg} from "@/libs/Utils.js";
import NProgress from "nprogress";


function encryptPassword(password) {
    const secretKey = import.meta.env.VITE_SECRET_KEY; // 从环境变量中获取 secretKey
    const iv = CryptoJS["lib"].WordArray.random(16); // 生成 16 字节的随机 IV
    const encrypted = CryptoJS["AES"].encrypt(password, CryptoJS["enc"].Hex.parse(secretKey), {
        iv: iv, // 直接使用生成的 IV
        mode: CryptoJS["mode"].CBC,
        padding: CryptoJS["pad"].Pkcs7,
    });
    // 返回密文和 IV
    return {
        encryptedPassword: encrypted.toString(), // 密文
        iv: iv.toString(), // 将 IV 转换为字符串以便传输 // CryptoJS["enc"].Hex
    };
}

export async function Info(){
    let info = null;
    try {
        const response = await server.get('/user/info');
        if (response['code'] === 200) {
            info = response.data;
            info.Avatar = '/api' + info.Avatar
            userInfoStore().setUserInfo(info);
            isLogin.value = true;
        }
    }catch {
        userInfoStore().clearUserInfo();
        isLogin.value = false;
    }
    return info;
}

export async function RegisterUser(info) {
    const user = { ...info };
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    const validations = [
        { valid: user.UserName === '' || user.Password === '' || user.Email === '', message: '请填写完整所需信息' },
        { valid: user.UserName.length < 2, message: '用户名需要至少2个字符' },
        { valid: user.Password.length < 6, message: '密码需要至少6位字符' },
        { valid: user.Password !== user.confirm, message: '两次密码输入不一致' },
        { valid: !emailRegex.test(user.Email), message: '邮箱格式不正确' }
    ];

    for (const validation of validations) {
        if (validation.valid) {
            await showMsg(validation.message, 'error');
            return false; // 或者 throw new Error(validation.message);
        }
    }

    const enc = encryptPassword(user.Password);
    user.Password = enc.encryptedPassword;
    user.iv = enc.iv;
    delete user.confirm;

    try {
        const response = await server.post('/user/register', user);
        await showMsg(response.data, 'success');
        return true;
    } catch (error) {
        return false;
    }
}

export async function UpdateUser(info) {
    const user = { ...info };
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    // 基本验证
    if (user.UserName && user.UserName.length < 2) {
        await showMsg('用户名需要至少2个字符', 'error');
        return false;
    }
    if (user.Email && !emailRegex.test(user.Email)) {
        await showMsg('邮箱格式不正确', 'error');
        return false;
    }

    // 处理密码更新
    if (user.newPassword) {
        if (user.newPassword.length < 6) {
            await showMsg('新密码需要至少6位字符', 'error');
            return false;
        }else if (user.newPassword !== user.confirmPassword) {
            await showMsg('两次密码输入不一致', 'error');
            return false;
        }else{
            // 加密新密码
            console.log(user.newPassword);
            const enc = encryptPassword(user.newPassword);
            user.Password = enc.encryptedPassword;
            user.iv = enc.iv;
        }
        
        
        
    }

    // 清理不需要的字段
    delete user.newPassword;
    delete user.confirmPassword;
    delete user.confirm;
    console.log(user);
    try {
        const response = await server.put('/user/update', user);
        if (response.data.code === 200) {
            await showMsg(response.data.message, 'success');
            // 更新本地用户信息
            const userStore = userInfoStore();
            userStore.setUserInfo({...userStore.getUserInfo(), ...user});
            return true;
        }
        return false;
    } catch (error) {
        return false;
    }
}


export async function LoginUser(info) {
    const user = { ...info };
    userInfoStore().clearUserInfo();
    tabStore().init();
    if (user.Email === '' ) {
        await showMsg('请输入邮箱', 'error');
        return false;
    }else if (user.Password === '') {
        await showMsg('请输入密码', 'error');
        return false;
    }

    const enc = encryptPassword(user.Password);
    user.Password = enc.encryptedPassword;
    user.iv = enc.iv;

    try {
        NProgress.start();
        const response = await server.post('/user/login', user);
        await showMsg(response.data.data, 'success');
        const info = await Info();
        userInfoStore().setUserInfo(info);
        isLogin.value = true;
        return true;
    } catch (error) {
        isLogin.value = false
        return false;
    }finally {
        NProgress.done();
    }
}

export async function CheckCookie(){
    try {
        const response = await server.get('/');
        if (response['code'] === 200 && response.data.message['refreshToken']) {
            return true;
        }
    }catch {
        isLogin.value = false;
    }
    return false;
}

export async function LogoutUser() {

    try {
        NProgress.start();
        const response = await server.get('/user/logout');
        await showMsg(response.data.message, 'success');
        userInfoStore().clearUserInfo();
        tabStore().init();
        isLogin.value = false;
        return true;
    } catch (error) {
        return false;
    }finally {
        NProgress.done();
    }
}

export async function UpdateAvatar(base64Image) {
    try {
        // 移除 base64 字符串的前缀
        const base64Data = base64Image.replace(/^data:image\/\w+;base64,/, '');
        
        const response = await server.put('/user/update/avatar', {
            Avatar: base64Data
        });
        
        await showMsg(response.data.message, 'success');
        return '/api' + response.data.avatarUrl;
    } catch (error) {
        return false;
    }
}

