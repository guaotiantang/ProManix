const express = require('express');
const router = express.Router();
const NodeList = require('../Models/NodeList');

// 注册节点
router.post('/register', async (req, res) => {
    try {
        const { NodeType, NodeName, Host, Port } = req.body;
        
        const existing = await NodeList.findOne({
            where: { NodeType, NodeName }
        });
        
        if (existing) {
            await existing.update({ Host, Port });
            return res.json({
                message: '节点已更新',
                code: 200,
                data: existing
            });
        }

        const node = await NodeList.create({ 
            NodeType,
            NodeName,
            Host, 
            Port
        });
        
        res.json({
            message: '添加成功',
            code: 200,
            data: node
        });
    } catch (error) {
        res.status(500).json({
            message: error.message,
            code: 500
        });
    }
});

// 注销节点
router.delete('/unregister', async (req, res) => {
    try {
        const { NodeType, NodeName } = req.body;
        
        const result = await NodeList.destroy({
            where: { NodeType, NodeName }
        });

        if (result === 0) {
            return res.status(404).json({
                message: '节点不存在',
                code: 404
            });
        }
        
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