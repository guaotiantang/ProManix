const express = require('express');
const router = express.Router();
const NDSList = require('../Models/NDSList');
const NDSGateways = require('../Models/NDSGateways');
const { Op } = require('sequelize');
const axios = require('axios');

// 异步通知函数
async function notifyPythonServices(action, config) {
    try {
        // 获取所有网关
        const gateways = await NDSGateways.findAll();
        
        // 使用 Promise.allSettled 并行发送通知，允许部分失败
        const notifyPromises = gateways.map(gateway => {
            const serviceUrl = `http://${gateway.Host}:${gateway.Port}`;
            return axios.post(`${serviceUrl}/nds/update-pool`, {
                action,
                config
            }).catch(error => {
                console.warn(`Failed to notify gateway ${serviceUrl}: ${error.message}`);
                return null; // 失败时返回null，不影响其他通知
            });
        });

        // 等待所有通知完成，不关心结果
        await Promise.allSettled(notifyPromises);
    } catch (error) {
        console.error('Error in notification process:', error);
        // 不抛出错误，让主流程继续执行
    }
}

// 包装通知函数，使其在单独的"线程"中执行
function notifyAsync(action, config) {
    // 使用 setImmediate 将通知任务放入下一个事件循环
    setImmediate(async () => {
        await notifyPythonServices(action, config);
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
        
        // 在删除之前获取完整记录用于通知
        const recordToDelete = await NDSList.findByPk(id);
        if (!recordToDelete) {
            return res.status(404).json({ message: '未找到要删除的记录' });
        }

        await NDSList.destroy({
            where: { ID: id }
        });

        // 异步通知，不等待结果
        notifyAsync('remove', recordToDelete);
        
        res.json({ message: '删除成功' });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

module.exports = router;
