const express = require('express');
const router = express.Router();
const NDSFileList = require('../Models/NDSFileList');
const NDSFiles = require('../Models/NDSFiles');
const fileQueue = require('../Libs/QueueManager');

// 清理NDS相关文件记录
router.delete('/clean/:nds_id', async (req, res) => {
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
router.post('/batch', async (req, res) => {
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
router.post('/remove', async (req, res) => {
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

        if (nds_id) {
            query.where = {
                NDSID: nds_id
            };
        }

        const files = await NDSFiles.findAll(query);
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

// 检查 NDS 是否有正在处理的任务
router.get('/check-tasks/:nds_id', async (req, res) => {
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
        data: hasTasks
    });
});

// 更新文件解析状态
router.post('/update-parsed', async (req, res) => {
    try {
        const { files } = req.body;
        
        // 验证请求参数
        if (!Array.isArray(files) || files.length === 0) {
            return res.status(400).json({
                code: 400,
                message: '无效的参数格式，需要提供文件列表'
            });
        }

        // 验证每个文件对象的格式
        for (const file of files) {
            if (!file.FileHash || typeof file.Parsed !== 'number') {
                return res.status(400).json({
                    code: 400,
                    message: '文件对象格式错误，需要包含 FileHash 和 Parsed 字段'
                });
            }
        }

        // 批量更新文件状态
        const updatePromises = files.map(file => 
            NDSFileList.update(
                { 
                    Parsed: file.Parsed,
                    UpdateTime: new Date()
                },
                {
                    where: { FileHash: file.FileHash }
                }
            )
        );

        await Promise.all(updatePromises);

        res.json({
            code: 200,
            message: '文件状态更新成功',
            data: {
                updatedCount: files.length
            }
        });

    } catch (error) {
        console.error('Update parsed status error:', error);
        res.status(500).json({
            code: 500,
            message: '更新文件状态失败',
            error: error.message
        });
    }
});

module.exports = router; 