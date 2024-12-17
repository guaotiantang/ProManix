import {server} from "@/libs/Utils.js";

// 获取NDS列表
export async function GetNDSList() {
    const response = await server.get('/mparser/nds/list');
    if (response.code === 200) {
        return response.data;
    }
    throw new Error(response.message || '获取数据失败')
}

// 新增NDS
export async function AddNDSItem(data) {
    const response = await server.post('/mparser/nds/add', data);
    if (response.code === 200) {
        return {
            success: true,
            data: response.data
        };
    }
    throw new Error(response.message || '添加失败');
}

// 更新NDS
export async function UpdateNDSItem(data) {
    const response = await server.post('/mparser/nds/update', data);
    if (response.code === 200) {
        return {
            success: true,
            data: response.data.data
        };
    }
    throw new Error(response.message || '更新失败');
}

// 删除NDS
export async function DeleteNDSItem(id) {
    const response = await server.delete(`/mparser/nds/remove/${id}`);
    if (response.code === 200) {
        return true;
    }
    return false;
}