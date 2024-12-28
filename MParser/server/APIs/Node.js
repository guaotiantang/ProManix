const express = require('express');
const router = express.Router();
const NodeList = require('../Models/NodeList');

// 注册节点
router.post('/register', async (req, res) => {
    try {
        const { NodeType, NodeName, Host, Port, Status } = req.body;
        
        // 验证必要字段
        if (!NodeType || !NodeName || !Host || !Port) {
            return res.status(400).json({
                code: 400,
                message: '缺少必要字段'
            });
        }

        const existing = await NodeList.findOne({
            where: { NodeType, NodeName }
        });

        if (existing) {
            await existing.update({ 
                Host, 
                Port, 
                Status: Status || 'Online',
                UpdateTime: new Date()
            });
            return res.json({
                code: 200,
                message: '节点已更新',
                data: existing
            });
        }

        const node = await NodeList.create({
            NodeType,
            NodeName,
            Host,
            Port,
            Status: Status || 'Online',
            CreateTime: new Date()
        });

        res.json({
            code: 200,
            message: '节点已注册',
            data: node
        });
    } catch (error) {
        res.status(500).json({
            code: 500,
            message: error.message
        });
    }
});

// 注销节点
router.delete('/unregister', async (req, res) => {
    try {
        const { NodeType, NodeName } = req.body;
        
        // 验证必要字段
        if (!NodeType || !NodeName) {
            return res.status(400).json({
                code: 400,
                message: '缺少必要字段'
            });
        }

        const node = await NodeList.findOne({
            where: { NodeType, NodeName }
        });

        if (!node) {
            return res.status(404).json({
                code: 404,
                message: '节点不存在'
            });
        }

        await node.update({
            Status: 'Offline',
            UpdateTime: new Date()
        });

        res.json({
            code: 200,
            message: '节点已注销',
            data: node
        });
    } catch (error) {
        res.status(500).json({
            code: 500,
            message: error.message
        });
    }
});

module.exports = router; 