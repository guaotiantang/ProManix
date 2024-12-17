
// noinspection JSUnusedGlobalSymbols

import axios from 'axios';
import {ElMessage, ElMessageBox} from "element-plus";

import * as ElementIcons from 'vue-icons-plus/ep';
import * as AiIcons from 'vue-icons-plus/ai';
import * as BsIcons from 'vue-icons-plus/bs';
import * as BiIcons from 'vue-icons-plus/bi';
import * as GrIcons from 'vue-icons-plus/gr';
import * as HiIcons from 'vue-icons-plus/hi';
import * as RiIcons from 'vue-icons-plus/ri';
import {isLogin} from "@/store/index.js";


const iconGroups = [ElementIcons, AiIcons, BsIcons, BiIcons, GrIcons, HiIcons, RiIcons];

const icons = iconGroups.reduce((acc, iconGroup) => ({ ...acc, ...Object.fromEntries(Object.entries(iconGroup)) }), {});

const resBody = {
    code: 200,
    data: null,
}

// 封装 axios 请求
const server = axios.create({
    baseURL: '/api',
    timeout: 60000,
    withCredentials: true,
});


// 响应拦截器
server.interceptors.response.use(
    response => {
        resBody.data = response.data || null;
        resBody.code = response.status;
        return resBody;
    },
    error => {
        resBody.code = error.response.status;
        resBody.data = error.response.data || error;
        try {
            showMsg(resBody.data.message || resBody.data, 'error').then();
        }finally {
            if (resBody.code === 401) isLogin.value = false;
        }

        return Promise.reject(resBody);
    }
);




async function showMsg(msg, type="success", duration=3000, showClose=true, center=true, offset=100, html=false) {
    // 显示消息提示
    // type: success, warning, info, error, inquire(询问消息)
    // duration: 显示时间（毫秒）
    // showClose: 是否显示关闭按钮
    // center: 是否居中显示
    // offset: 偏移量（像素）

    try {
        if (type === 'inquire') {
            try {
                await ElMessageBox.confirm(msg, 'Tip', {
                    confirmButtonText: '确定',
                    cancelButtonText: '取消',
                    dangerouslyUseHTMLString: true, //启动HTML片段处理,用于处理<br>换行
                });
                return true;  // 用户点击了“确定”
            } catch {
                return false;  // 用户点击了“取消”或关闭了对话框
            }
        } else {
            ElMessage({
                message: msg,
                type: type,
                duration: duration,
                showClose: showClose,
                center: center,
                offset: offset,
                dangerouslyUseHTMLString: html, //启动HTML片段处理,用于处理<br>换行
            });
            return true;
        }
    } catch {
        return false;
    }
}



export {server, showMsg, iconGroups, icons};
