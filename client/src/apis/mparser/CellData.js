import {server} from "@/libs/Utils.js";

// 获取小区数据列表
export async function GetCellDataList(page = 1, pageSize = 50, field = 'all', keyword = '') {
    const response = await server.get('/mparser/celldata/list', {
        params: {
            page,
            pageSize,
            field,
            keyword
        }
    });
    if (response.code === 200) {
        return response.data;
    }
    throw new Error(response.message || '获取数据失败')
}

// 新增小区数据
export async function AddCellData(data) {
    const response = await server.post('/mparser/celldata/add', data);
    return response.code === 200;
}

// 更新小区数据
export async function UpdateCellData(data) {
    const response = await server.post('/mparser/celldata/update', data);
    return response.code === 200;
}

// 删除小区数据
export async function DeleteCellData(cgi) {
    const response = await server.delete(`/mparser/celldata/remove/${cgi}`);
    return response.code === 200;
}

// 批量删除
export async function BatchDeleteCellData(cgis) {
    const response = await server.post('/mparser/celldata/batchDelete', { cgis });
    return response.code === 200;
}

// 导出Excel
export async function ExportExcel() {
    const response = await server.get('/mparser/celldata/export', {
        responseType: 'blob'
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'CellData.xlsx');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    return true;
}

// 检查CGI是否存在
export async function CheckCGIExists(cgi) {
    const response = await server.get(`/mparser/celldata/check/${cgi}`);
    return response.data.exists;
}

export async function Test(data) {
    const response = await server.post('/mparser/celldata/test', data);
    return response.data.message;
}

// 上传Excel文件
export async function UploadExcel(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const response = await server.post('/mparser/celldata/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data'
            },
            maxBodyLength: Infinity,
            maxContentLength: Infinity,
            timeout: 0
        });
        
        if (response.code === 200) {
            return response.data;
        }
        throw new Error(response.message || '上传失败');
    } catch (error) {
        console.error('上传错误:', error);
        throw error;
    }
}
