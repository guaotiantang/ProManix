const express = require('express');
const router = express.Router();
const NDSList = require('../Models/NDSList');
const NodeList = require('../Models/NodeList');
const { Op } = require('sequelize');
const axios = require('axios');
const NDSFileList = require('../Models/NDSFileList');

// 异步通知函数
async function notifyServices(action, config) {
    try {
        // 获取所有网关和扫描器节点
        const nodes = await NodeList.findAll({
            where: { 
                NodeType: { [Op.in]: ['NDSGateway', 'NDSScanner'] }
            }
        });
        
        const notifyPromises = nodes.map(node => {
            const serviceUrl = `http://${node.Host}:${node.Port}`;
            const endpoint = node.NodeType === 'NDSGateway' 
                ? '/nds/update-pool'
                : '/control/nds';
            
            return axios.post(`${serviceUrl}${endpoint}`, {
                action,
                config
            }).catch(error => {
                console.warn(`Failed to notify ${node.NodeType} ${serviceUrl}: ${error.message}`);
                return null;
            });
        });

        await Promise.allSettled(notifyPromises);
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
            where: { NDSName: data.NDSName }
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

// 添加文件同步接口
router.post('/files/sync', async (req, res) => {
    try {
        const { nds_id, files } = req.body;
        
        // 获取数据库中现有文件
        const existingFiles = await NDSFileList.findAll({
            where: { NDSID: nds_id }
        });
        
        const existingPaths = new Set(existingFiles.map(f => f.FilePath));
        const newPaths = new Set(files);
        
        // 需要删除的文件
        const toDelete = existingFiles.filter(f => !newPaths.has(f.FilePath));
        
        // 需要添加的文件
        const toAdd = files.filter(f => !existingPaths.has(f));
        
        // 删除不存在的文件
        await NDSFileList.destroy({
            where: {
                ID: toDelete.map(f => f.ID)
            }
        });
        
        // 添加新文件
        if (toAdd.length > 0) {
            await NDSFileList.bulkCreate(
                toAdd.map(filePath => ({
                    NDSID: nds_id,
                    FilePath: filePath,
                    DataType: filePath.toLowerCase().includes('mdt') ? 'MDT' : 'MRO',
                    FileTime: new Date(),
                    Parsed: 0
                }))
            );
        }
        
        res.json({
            message: 'Sync successful',
            new_files: toAdd.length,
            deleted_files: toDelete.length
        });
    } catch (error) {
        res.status(500).json({
            message: error.message
        });
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

module.exports = router;
