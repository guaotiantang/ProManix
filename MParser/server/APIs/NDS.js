const express = require('express');
const router = express.Router();
const NDSList = require('../Models/NDSList');
const NodeList = require('../Models/NodeList');
const { Op } = require('sequelize');
const axios = require('axios');
const NDSFileList = require('../Models/NDSFileList');
const { sequelize } = require('../Libs/DataBasePool');


// 异步通知函数
async function notifyServices(action, config) {
    try {
        const nodes = await NodeList.findAll({
            where: { 
                NodeType: { [Op.in]: ['NDSGateway', 'NDSScanner'] }
            }
        });
        
        const notifyPromises = nodes.map(node => {
            const serviceUrl = `http://${node.Host}:${node.Port}`;
            const endpoint = node.NodeType === 'NDSGateway' 
                ? '/nds/update-pool'
                : '/control';
            
            // 根据不同操作类型构造不同的请求体
            const requestBody = {
                action: action,  // 保持原始action类型
                config: {
                    ...config,
                    operation: action  // 添加操作类型标记
                }
            };
            
            return axios.post(`${serviceUrl}${endpoint}`, requestBody)
                .catch(error => {
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

// 获取差异文件并删除不存在的文件(使用数据库比较)
router.post('/files/diff', async (req, res) => {
    let transaction;
    try {
        transaction = await sequelize.transaction();
        const { nds_id, files } = req.body;
        if (!nds_id || !files || files.length === 0) {
            return res.status(400).json({ message: '缺少必要参数' });
        }

        // 创建临时表
        await sequelize.query(`
            CREATE TEMPORARY TABLE temp_files (
                FilePath VARCHAR(250) NOT NULL,
                INDEX (FilePath)  -- 添加索引提高性能
            )
        `, { transaction });

        // 分批导入数据
        const batchSize = 1000;
        for (let i = 0; i < files.length; i += batchSize) {
            const batch = files.slice(i, i + batchSize);
            await sequelize.query(
                `INSERT INTO temp_files (FilePath) VALUES ${
                    batch.map(() => '(?)').join(',')
                }`,
                {
                    replacements: batch,
                    transaction,
                    type: sequelize.QueryTypes.INSERT
                }
            );
        }

        // 删除不存在的文件
        const [result] = await sequelize.query(`
            DELETE FROM NDSFileList 
            WHERE NDSID = :nds_id 
            AND FilePath NOT IN (SELECT FilePath FROM temp_files)
        `, {
            replacements: { nds_id },
            transaction,
            type: sequelize.QueryTypes.DELETE
        });

        // 获取新文件列表
        const [newFiles] = await sequelize.query(`
            SELECT DISTINCT t.FilePath 
            FROM temp_files t
            LEFT JOIN NDSFileList n ON n.FilePath = t.FilePath AND n.NDSID = :nds_id
            WHERE n.ID IS NULL
        `, {
            replacements: { nds_id },
            transaction,
            type: sequelize.QueryTypes.SELECT
        });

        // 提交事务
        await transaction.commit();

        // 返回结果
        res.json({
            new_files: newFiles.map(file => ({
                NDSID: nds_id,
                FilePath: file.FilePath
            })),
            deleted_count: result,  // 添加删除的文件数量
            total_files: files.length
        });

    } catch (error) {
        if (error.name === 'SequelizeUniqueConstraintError') {
            return res.status(409).json({
                code: 409,
                message: '记录已存在'
            });
        }
        
        res.status(500).json({
            code: 500,
            message: '数据库操作失败',
            detail: error.message
        });
    } finally {
        // 确保临时表被删除，使用独立的连接
        try {
            await sequelize.query('DROP TEMPORARY TABLE IF EXISTS temp_files', {
                raw: true,
                type: sequelize.QueryTypes.RAW
            });
        } catch (e) {
            console.log(e.message);
        }
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
