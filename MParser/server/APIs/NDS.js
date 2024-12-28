// noinspection JSUnresolvedReference

const express = require('express');
const router = express.Router();
const NDSList = require('../Models/NDSList');
const NodeList = require('../Models/NodeList');
const { Op } = require('sequelize');
const axios = require('axios');
const NDSFileList = require('../Models/NDSFileList');
const NDSFiles = require('../Models/NDSFiles');
const fileQueue = require('../Libs/QueueManager');




// 异步通知函数
async function notifyServices(action, config) {
    try {
        const nodes = await NodeList.findAll({
            where: { 
                NodeType: { [Op.in]: ['NDSGateway', 'NDSScanner'] }
            }
        });
        
        // 分离网关和扫描器节点
        const gatewayNodes = nodes.filter(node => node.NodeType === 'NDSGateway' && node.Status === "Online");
        const scannerNodes = nodes.filter(node => node.NodeType === 'NDSScanner' && node.Status === "Online");
        
        // 处理 config 中的 dataValues
        const configData = config.dataValues || config;
        
        // 构造请求体
        const requestBody = {
            action: action,
            config: {
                ...configData,
                operation: action
            }
        };
        
        // 先通知所有网关节点
        if (gatewayNodes.length > 0) {
            const gatewayPromises = gatewayNodes.map(node => {
                const serviceUrl = `http://${node.Host}:${node.Port}`;
                return axios.post(`${serviceUrl}/nds/update-pool`, requestBody)
                    .catch(error => {
                        console.warn(`Failed to notify Gateway ${serviceUrl}: ${error.message}`);
                        return null;
                    });
            });
            await Promise.all(gatewayPromises);
        }
        
        // 再通知所有扫描器节点
        if (scannerNodes.length > 0) {
            const scannerPromises = scannerNodes.map(node => {
                const serviceUrl = `http://${node.Host}:${node.Port}`;
                return axios.post(`${serviceUrl}/control`, requestBody)
                    .catch(error => {
                        console.warn(`Failed to notify Scanner ${serviceUrl}: ${error.message}`);
                        return null;
                    });
            });
            await Promise.all(scannerPromises);
        }

    } catch (error) {
        console.error('Error in notification process:', error);
    }
}

// 包装通知函数，使其在单独的"线程"中执行
function notifyAsync(action, config) {
    // 使用 setImmediate 将通知任务放入下一个事件循环
    setImmediate(async () => {
        await notifyServices(action, config);
    });
}

// 获取列表
router.get('/list', async (req, res) => {
    try {
        const { page = 1, pageSize = 50, field = 'all', keyword = '' } = req.query;
        const where = keyword ? {
            [Op.or]: field === 'all' ? [
                { NDSName: { [Op.like]: `%${keyword}%` } },
                { Address: { [Op.like]: `%${keyword}%` } },
                { Protocol: { [Op.like]: `%${keyword}%` } },
                { Port: isNaN(keyword) ? -1 : parseInt(keyword) }
            ] : { [field]: isNaN(keyword) ? { [Op.like]: `%${keyword}%` } : parseInt(keyword) }
        } : {};

        const { count, rows } = await NDSList.findAndCountAll({
            where,
            offset: (page - 1) * pageSize,
            limit: parseInt(pageSize),
            order: [['ID', 'ASC']]
        });

        res.json({ total: count, list: rows });
    } catch (error) {
        console.error('获取列表失败:', error);
        res.status(500).json({ message: error.message });
    }
});

// 新增
router.post('/add', async (req, res) => {
    try {
        const data = req.body;
        
        const existingRecord = await NDSList.findOne({
            where: { NDSName: data.NDSName },
            attributes: ['ID', 'NDSName'],
            raw: true
        });
        
        if (existingRecord) {
            return res.status(400).json({ 
                message: 'NDS名称已存在，不能重复添加',
                code: 400
            });
        }

        const newNDS = await NDSList.create({
            ...data,
            Status: 1,
            Switch: 1,
            AddTime: new Date()
        });

        const fullRecord = await NDSList.findByPk(newNDS.ID);

        // 异步通知，不等待结果
        if (newNDS.Switch === 1) {
            notifyAsync('add', fullRecord);
        }

        res.json({ 
            message: '新增成功',
            code: 200,
            data: fullRecord
        });
    } catch (error) {
        res.status(500).json({ 
            message: error.message,
            code: 500
        });
    }
});

// 更新
router.post('/update', async (req, res) => {
    try {
        const data = req.body;
        if (data.NDSName) {
            const existingRecord = await NDSList.findOne({
                where: { 
                    NDSName: data.NDSName,
                    ID: { [Op.ne]: data.ID }
                }
            });
            
            if (existingRecord) {
                return res.status(400).json({ 
                    message: 'NDS名称已存在，不能重复',
                    code: 400
                });
            }
        }

        await NDSList.update(data, {
            where: { ID: data.ID }
        });
        
        const updatedNDS = await NDSList.findByPk(data.ID);
        if (!updatedNDS) {
            return res.status(404).json({ 
                message: '未找到要更新的记录',
                code: 404 
            });
        }

        // 异步通知，不等待结果
        notifyAsync('update', updatedNDS);
        
        res.json({ 
            message: '更新成功',
            code: 200,
            data: updatedNDS
        });
    } catch (error) {
        res.status(500).json({ 
            message: error.message,
            code: 500 
        });
    }
});

// 更新状态
router.post('/updateStatus', async (req, res) => {
    try {
        const { ID, Status, Switch } = req.body;
        
        if ((Status === undefined && Switch === undefined) || !ID) {
            return res.status(400).json({ message: '缺少必要参数' });
        }

        const updateData = {};
        if (Status !== undefined) updateData.Status = Status;
        if (Switch !== undefined) updateData.Switch = Switch;

        await NDSList.update(updateData, { where: { ID } });
        
        const updatedNDS = await NDSList.findByPk(ID);
        if (!updatedNDS) {
            return res.status(404).json({ 
                message: '未找到要更新的记录',
                code: 404 
            });
        }

        // 如果Switch发生变化，需要通知Python服务
        if (Switch !== undefined) {
            notifyAsync('update', updatedNDS);
        }

        // 如果Switch变为0，通知Scanner停止扫描
        if (Switch === 0) {
            const gateways = await NodeList.findAll({
                where: { NodeType: 'NDSGateway' }
            });
            await Promise.all(gateways.map(gateway => {
                const scannerUrl = `http://${gateway.Host}:10002`;  // 假设Scanner服务端口为10002
                return axios.post(`${scannerUrl}/control/nds/${ID}/stop`)
                    .catch(e => console.warn(`Failed to stop scanner: ${e.message}`));
            }));
        }

        res.json({ 
            message: '更新成功',
            code: 200,
            data: updatedNDS
        });
    } catch (error) {
        res.status(500).json({ 
            message: error.message,
            code: 500 
        });
    }
});

// 删除
router.delete('/remove/:id', async (req, res) => {
    try {
        const { id } = req.params;
        
        // 先停止扫描
        const gateways = await NodeList.findAll({
            where: { NodeType: 'NDSGateway' }
        });
        await Promise.all(gateways.map(gateway => {
            const scannerUrl = `http://${gateway.Host}:10002`;
            return axios.post(`${scannerUrl}/control/nds/${id}/stop`)
                .catch(e => console.warn(`Failed to stop scanner: ${e.message}`));
        }));

        // 然后删除记录
        await NDSList.destroy({ where: { ID: id } });
        
        // 异步通知，不等待结果
        notifyAsync('remove', recordToDelete);
        
        res.json({ message: '删除成功' });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});


// 清理NDS相关文件记录
router.delete('/files/clean/:nds_id', async (req, res) => {
    try {
        const { nds_id } = req.params;
        
        await NDSFileList.destroy({
            where: { NDSID: nds_id }
        });
        
        res.json({
            message: 'Files cleaned successfully',
            code: 200
        });
    } catch (error) {
        res.status(500).json({
            message: error.message,
            code: 500
        });
    }
});

// 批量添加文件记录
router.post('/files/batch', async (req, res) => {
    const { files } = req.body;
    
    if (!Array.isArray(files)) {
        return res.status(400).json({ 
            code: 400,
            message: '无效的文件数据' 
        });
    }

    // 分批处理，每批1000条
    const BATCH_SIZE = 1000;
    const taskIds = [];

    for (let i = 0; i < files.length; i += BATCH_SIZE) {
        const batch = files.slice(i, i + BATCH_SIZE);
        const taskId = `${Date.now()}_${i}`;
        
        await fileQueue.enqueue({
            type: 'INSERT',
            data: { files: batch },
            taskId
        });
        
        taskIds.push({
            taskId,
            filesCount: batch.length
        });
    }

    res.json({
        code: 200,
        message: 'Tasks added to queue',
        data: {
            totalFiles: files.length,
            batches: taskIds
        }
    });
});


// 批量删除文件记录
router.post('/files/remove', async (req, res) => {
    const { nds_id, files } = req.body;
    
    if (!nds_id || !Array.isArray(files)) {
        return res.status(400).json({ 
            code: 400,
            message: '参数错误' 
        });
    }

    // 转换文件格式，添加 NDSID
    const fileRecords = files.map(filePath => ({
        NDSID: nds_id,
        FilePath: filePath
    }));

    // 分批处理，每批1000条
    const BATCH_SIZE = 1000;
    const taskIds = [];

    for (let i = 0; i < fileRecords.length; i += BATCH_SIZE) {
        const batch = fileRecords.slice(i, i + BATCH_SIZE);
        const taskId = `${Date.now()}_${i}`;
        
        await fileQueue.enqueue({
            type: 'DELETE',
            data: { files: batch },
            taskId
        });
        
        taskIds.push({
            taskId,
            filesCount: batch.length
        });
    }

    res.json({
        code: 200,
        message: 'Tasks added to queue',
        data: {
            totalFiles: files.length,
            batches: taskIds
        }
    });
});
// 获取NDS文件清单
router.get('/files', async (req, res) => {
    try {
        const { nds_id } = req.query;
        let query = {
            attributes: ['FilePath'],
            order: [['FilePath', 'ASC']]
        };

        // 如果指定了NDS_ID，添加条件过滤
        if (nds_id) {
            query.where = {
                NDSID: nds_id
            };
        }

        const files = await NDSFiles.findAll(query);
        
        // 只返回文件路径列表
        const filePaths = files.map(file => file.FilePath);

        res.json({
            code: 200,
            data: filePaths
        });
    } catch (error) {
        console.error('Error fetching NDS files:', error);
        res.status(500).json({
            code: 500,
            error: 'Failed to fetch NDS files'
        });
    }
});

// 检查NDS连接
router.post('/check', async (req, res) => {
    try {
        const { nds_id, config } = req.body;
        let ndsConfig;

        // 1. 如果提供了 nds_id，优先使用数据库中的配置
        if (nds_id) {
            const ndsRecord = await NDSList.findByPk(nds_id);
            if (!ndsRecord) {
                return res.status(404).json({
                    code: 404,
                    message: `NDS ID ${nds_id} not found`
                });
            }
            ndsConfig = {
                Protocol: ndsRecord.Protocol,
                Address: ndsRecord.Address,
                Port: ndsRecord.Port,
                Account: ndsRecord.Account,
                Password: ndsRecord.Password
            };
        }
        // 2. 如果没有 nds_id 但提供了配置，使用提供的配置
        else if (config) {
            const requiredFields = ['Protocol', 'Address', 'Port', 'Account', 'Password'];
            const missingFields = requiredFields.filter(field => !(field in config));
            
            if (missingFields.length > 0) {
                return res.status(400).json({
                    code: 400,
                    message: `Missing required fields: ${missingFields.join(', ')}`
                });
            }
            ndsConfig = config;
        }
        // 3. 如果都没有提供，返回错误
        else {
            return res.status(400).json({
                code: 400,
                message: 'Either nds_id or config must be provided'
            });
        }

        // 4. 查找可用的网关节点
        const gateway = await NodeList.findOne({
            where: { 
                NodeType: 'NDSGateway'
            }
        });

        if (!gateway) {
            return res.status(503).json({
                code: 503,
                message: 'No available gateway node'
            });
        }

        // 5. 先检查网关状态
        try {
            const gatewayStatus = await axios.get(`http://${gateway.Host}:${gateway.Port}/`);
            if (gatewayStatus.data.code !== 200) {
                return res.status(503).json({
                    code: 503,
                    message: 'Gateway is not ready',
                    error: gatewayStatus.data.message
                });
            }
        } catch (error) {
            return res.status(503).json({
                code: 503,
                message: 'Gateway is not accessible',
                error: error.message
            });
        }

        // 6. 调用网关的检查接口
        const response = await axios.post(
            `http://${gateway.Host}:${gateway.Port}/check`,
            ndsConfig
        );

        // 7. 返回检查结果
        return res.json(response.data);

    } catch (error) {
        console.error('Check NDS connection error:', error);
        return res.status(500).json({
            code: 500,
            message: 'Failed to check NDS connection',
            error: error.message
        });
    }
});

// 检查 NDS 是否有正在处理的任务
router.get('/files/check-tasks/:nds_id', async (req, res) => {
    const { nds_id } = req.params;
    
    if (!nds_id) {
        return res.status(400).json({
            code: 400,
            message: 'nds_id is required'
        });
    }

    const hasTasks = fileQueue.hasNDSTasks(parseInt(nds_id));
    
    res.json({
        code: 200,
        data: hasTasks  // true 表示有任务在处理，false 表示没有任务
    });
});

module.exports = router;
