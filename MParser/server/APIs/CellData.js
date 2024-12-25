const express = require('express');
const router = express.Router();
const CellData = require('../Models/CellData');
const xlsx = require('xlsx');
const { Op } = require('sequelize');
const { sequelize } = require('../Libs/DataBasePool');

// 获取列表
router.get('/list', async (req, res) => {
    try {
        const { page = 1, pageSize = 50, field, keyword } = req.query;

        let where = {};
        if (field && keyword && field !== 'all') {
            where[field] = {
                [Op.like]: `%${keyword}%`
            };
        } else if (keyword) {
            where = {
                [Op.or]: [
                    { CGI: { [Op.like]: `%${keyword}%` } },
                    { eNBName: { [Op.like]: `%${keyword}%` } },
                    { userLabel: { [Op.like]: `%${keyword}%` } }
                ]
            };
        }

        const { count, rows } = await CellData.findAndCountAll({
            where,
            offset: (page - 1) * pageSize,
            limit: parseInt(pageSize),
            order: [['CGI', 'ASC']]
        });

        // 添加数据类型转换
        const formattedRows = rows.map(row => {
            const data = row.toJSON();
            // 确保数值类型的字段正确转换
            data.Latitude = parseFloat(data.Latitude);
            data.Longitude = parseFloat(data.Longitude);
            data.PCI = parseInt(data.PCI);
            data.eNodeBID = parseInt(data.eNodeBID);
            data.Azimuth = parseFloat(data.Azimuth);
            data.Earfcn = parseInt(data.Earfcn);
            data.Freq = parseInt(data.Freq);
            return data;
        });

        res.json({
            total: count,
            list: formattedRows
        });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

// 新增
router.post('/add', async (req, res) => {
    try {
        const data = req.body;

        // 检查 CGI 是否已存在
        const existingRecord = await CellData.findOne({
            where: { CGI: data.CGI }
        });

        if (existingRecord) {
            return res.status(400).json({
                message: 'CGI已存在, 不能重复添加'
            });
        }

        await CellData.create(data);
        res.json({
            message: '新增成功',
            code: 200
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
        const result = await CellData.update(data, {
            where: { CGI: data.CGI }
        });

        if (result[0] === 0) {
            return res.status(404).json({ message: '没有字段需要更新' });
        }

        res.json({ message: '更新成功' });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

// 删除
router.delete('/remove/:cgi', async (req, res) => {
    try {
        const { cgi } = req.params;
        const result = await CellData.destroy({
            where: { CGI: cgi }
        });

        if (result === 0) {
            return res.status(404).json({ message: '未找到要删除的记录' });
        }

        res.json({ message: '删除成功' });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

// 批量删除
router.post('/batchDelete', async (req, res) => {
    try {
        const { cgis } = req.body;
        if (!Array.isArray(cgis) || cgis.length === 0) {
            return res.status(400).json({ message: '请提供有效的CGI列表' });
        }

        const result = await CellData.destroy({
            where: {
                CGI: {
                    [Op.in]: cgis
                }
            }
        });

        res.json({
            message: '批量删除成功',
            deletedCount: result
        });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

// 检查CGI是否存在
router.get('/check/:cgi', async (req, res) => {
    try {
        const { cgi } = req.params;
        const exists = await CellData.findOne({
            where: { CGI: cgi }
        });

        res.json({ exists: !!exists });
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

// 文件上传
router.post('/upload', async (req, res) => {
    const transaction = await sequelize.transaction();

    try {
        if (!req.files || !req.files.file) {
            return res.status(400).json({ message: '没有上传文件' });
        }

        const workbook = xlsx.read(req.files.file.data);
        if (!workbook.SheetNames.includes('CellData')) {
            return res.status(400).json({ message: '文件中未找到 CellData 工作表' });
        }

        const sheet = workbook.Sheets['CellData'];
        const data = xlsx.utils.sheet_to_json(sheet);
        const results = {
            total: data.length,
            inserted: 0,
            updated: 0,
            unchanged: 0,
            failed: 0
        };

        // 批量查询所有CGI
        const cgis = data.map(row => row.CGI);
        const existingRecords = await CellData.findAll({
            where: { CGI: cgis },
            transaction
        });

        // 转换为Map以便快速查找
        const existingMap = new Map(
            existingRecords.map(record => [record.CGI, record])
        );

        // 准备批量操作的数组
        const toCreate = [];
        const toUpdate = [];

        // 分类处理
        for (const row of data) {
            try {
                const existingRecord = existingMap.get(row.CGI);

                if (existingRecord) {
                    const hasChanges = Object.keys(row).some(key => {
                        if (key === 'CGI') return false;
                        if (typeof row[key] === 'number') {
                            return Math.abs(row[key] - existingRecord[key]) > 0.0000001;
                        }
                        return row[key] !== existingRecord[key];
                    });

                    if (hasChanges) {
                        toUpdate.push({
                            ...row,
                            id: existingRecord.id
                        });
                        results.updated++;
                    } else {
                        results.unchanged++;
                    }
                } else {
                    toCreate.push(row);
                    results.inserted++;
                }
            } catch (error) {
                results.failed++;
                console.error('数据处理错误:', error);
            }
        }

        // 批量执行创建和更新
        if (toCreate.length > 0) {
            await CellData.bulkCreate(toCreate, { transaction });
        }

        if (toUpdate.length > 0) {
            await Promise.all(
                toUpdate.map(row =>
                    CellData.update(row, {
                        where: { CGI: row.CGI },
                        transaction
                    })
                )
            );
        }

        await transaction.commit();

        const allSkipped = results.failed === 0;
        const successRate = allSkipped
            ? '100%'
            : `${(((results.inserted + results.updated) / results.total) * 100).toFixed(2)}%`;

        res.json({
            message: '文件处理成功',
            results: {
                ...results,
                success: results.inserted + results.updated,
                successRate
            }
        });
    } catch (error) {
        await transaction.rollback();
        res.status(500).json({
            message: '文件处理失败',
            error: error.message
        });
    }
});


// 导出
router.get('/export', async (_req, res) => {
    try {
        const data = await CellData.findAll();
        const workbook = xlsx.utils.book_new();
        const worksheet = xlsx.utils.json_to_sheet(data.map(item => item.toJSON()));
        xlsx.utils.book_append_sheet(workbook, worksheet, 'CellData');

        res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        res.setHeader('Content-Disposition', 'attachment; filename=CellData.xlsx');
        res.send(xlsx.write(workbook, { type: 'buffer', bookType: 'xlsx' }));
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
});

module.exports = router;
