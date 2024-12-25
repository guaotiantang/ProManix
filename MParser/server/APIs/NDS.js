const express = require('express');
const router = express.Router();
const NDSList = require('../Models/NDSList');
const NodeList = require('../Models/NodeList');
const { Op } = require('sequelize');
const axios = require('axios');
const NDSFileList = require('../Models/NDSFileList');
const NDSFiles = require('../Models/NDSFiles');
const { sequelize } = require('../Libs/DataBasePool');
const { Semaphore, Mutex } = require('async-mutex');

// 创建全局信号量，限制总并发数
const globalSemaphore = new Semaphore(10);  // 限制总并发为10
// 创建队列锁，确保请求按顺序处理
const queueMutex = new Mutex();
// 创建互斥锁，确保请求串行处理
const batchMutex = new Mutex();

// 异步通知函数
async function notifyServices(action, config) {
    try {
        const nodes = await NodeList.findAll({
            where: { 
                NodeType: { [Op.in]: ['NDSGateway', 'NDSScanner'] }
            }
        });
        
        // 分离网关和扫描器节点
        const gatewayNodes = nodes.filter(node => node.NodeType === 'NDSGateway');
        const scannerNodes = nodes.filter(node => node.NodeType === 'NDSScanner');
        
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

// 获取差异文件并删除不存在的文件(使用数据库比较)
router.post('/files/diff', async (req, res) => {
    let transaction;
    try {
        const { nds_id, files } = req.body;
        
        if (!nds_id || !Array.isArray(files) || files.length === 0) {
            return res.status(400).json({ message: '缺少必要参数或参数格式错误' });
        }

        transaction = await sequelize.transaction();

        // 创建临时表，添加类型字段
        await sequelize.query(`
            CREATE TEMPORARY TABLE temp_files (
                FilePath VARCHAR(250) NOT NULL,
                DataType VARCHAR(20) NOT NULL,
                INDEX (FilePath)
            )
        `, { transaction });

        // 分批导入数据，包含文件类型
        const batchSize = 1000;
        const values = files.map(file => 
            `(${sequelize.escape(file.path)}, ${sequelize.escape(file.type)})`
        );
        
        for (let i = 0; i < values.length; i += batchSize) {
            const batch = values.slice(i, i + batchSize);
            await sequelize.query(
                `INSERT INTO temp_files (FilePath, DataType) VALUES ${batch.join(',')}`,
                { transaction }
            );
        }

        // 删除不存在的文件，同时匹配文件类型
        await sequelize.query(`
            DELETE FROM NDSFileList 
            WHERE NDSID = :nds_id 
            AND NOT EXISTS (
                SELECT 1 FROM temp_files 
                WHERE temp_files.FilePath = NDSFileList.FilePath 
                AND temp_files.DataType = NDSFileList.DataType
            )
        `, {
            replacements: { nds_id },
            transaction
        });

        // 获取新文件列表，包含类型信息
        const [newFiles] = await sequelize.query(`
            SELECT DISTINCT t.FilePath, t.DataType
            FROM temp_files t
            LEFT JOIN NDSFileList n ON 
                n.FilePath = t.FilePath 
                AND n.NDSID = :nds_id
                AND n.DataType = t.DataType
            WHERE n.FileHash IS NULL
        `, {
            replacements: { nds_id },
            transaction
        });

        await transaction.commit();

        res.json({
            new_files: newFiles.map(file => ({
                NDSID: nds_id,
                FilePath: file.FilePath,
                DataType: file.DataType
            }))
        });

    } catch (error) {
        if (transaction && !transaction.finished) {
            await transaction.rollback();
        }
        
        res.status(500).json({
            code: 500,
            message: '数据库操作失败',
            detail: error.message
        });
    } finally {
        try {
            await sequelize.query('DROP TEMPORARY TABLE IF EXISTS temp_files');
        } catch (e) {
            console.error('Error dropping temporary table:', e);
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

// 批量添加文件记录
router.post('/files/batch', async (req, res) => {
    // 获取互斥锁
    // const release = await batchMutex.acquire();
    let transaction;
    
    try {
        const { files } = req.body;
        
        if (!Array.isArray(files) || files.length === 0) {
            // release();
            return res.status(400).json({ message: '无效的文件数据' });
        }

        transaction = await sequelize.transaction();
        
        // 使用原生SQL进行批量插入
        const values = files.map(file => `(
            MD5(CONCAT(
                ${sequelize.escape(file.NDSID)}, '_',
                ${sequelize.escape(file.FilePath)}, '_',
                ${sequelize.escape(file.DataType)}, '_',
                ${sequelize.escape(file.SubFileName)}
            )),
            ${sequelize.escape(file.NDSID)},
            ${sequelize.escape(file.FilePath)},
            ${sequelize.escape(file.FileTime)},
            ${sequelize.escape(file.DataType)},
            ${sequelize.escape(file.eNodeBID)},
            ${sequelize.escape(file.SubFileName)},
            ${sequelize.escape(file.HeaderOffset)},
            ${sequelize.escape(file.CompressSize)},
            ${sequelize.escape(file.FileSize)},
            ${sequelize.escape(file.FlagBits)},
            ${sequelize.escape(file.CompressType)},
            ${sequelize.escape(file.Parsed)},
            NOW(),
            NOW()
        )`);

        // 分批执行，每批1000条
        const batchSize = 1000;
        let insertedCount = 0;

        // 串行处理每个批次
        for (let i = 0; i < values.length; i += batchSize) {
            const batch = values.slice(i, i + batchSize);
            const result = await sequelize.query(`
                INSERT IGNORE INTO NDSFileList (
                    FileHash,
                    NDSID, FilePath, FileTime, DataType, 
                    eNodeBID, SubFileName, HeaderOffset, 
                    CompressSize, FileSize, FlagBits, 
                    CompressType, Parsed, CreateTime, UpdateTime
                ) VALUES ${batch.join(',')}
            `, { transaction });
            
            insertedCount += result[0].affectedRows || 0;
        }

        await transaction.commit();
        
        res.json({
            message: '批量添加成功',
            total: files.length,
            created: insertedCount
        });
        
    } catch (error) {
        if (transaction) await transaction.rollback();
        
        res.status(500).json({
            message: '批量添加失败',
            error: error.message
        });
    // } finally {
    //     // 释放互斥锁
    //     release();
    }
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

module.exports = router;
