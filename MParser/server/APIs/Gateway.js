const express = require('express');
const router = express.Router();
const NDSGateways = require('../Models/NDSGateways');

// 添加网关
router.post('/add', async (req, res) => {
    try {
        const { Host, Port } = req.body;
        
        // 检查是否已存在
        const existing = await NDSGateways.findOne({
            where: { Host, Port }
        });
        
        if (existing) {
            return res.json({
                message: '网关已存在',
                code: 200,
                data: existing
            });
        }

        const gateway = await NDSGateways.create({ Host, Port });
        
        res.json({
            message: '添加成功',
            code: 200,
            data: gateway
        });
    } catch (error) {
        res.status(500).json({
            message: error.message,
            code: 500
        });
    }
});

// 删除网关
router.delete('/remove', async (req, res) => {
    try {
        const { Host, Port } = req.body;
        
        await NDSGateways.destroy({
            where: { Host, Port }
        });
        
        res.json({
            message: '删除成功',
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