// noinspection JSIgnoredPromiseFromCall

const { Mutex } = require('async-mutex');
const { sequelize, Sequelize } = require('./DataBasePool');
const NDSFileList = require('../Models/NDSFileList');
const EnbFileList = require('../Models/EnbFileList');   
const NodeList = require('../Nodes/NodeList');
const { Op } = require('sequelize');
const crypto = require('crypto');
const axios = require('axios');

class FileOperationQueue {
    constructor() {
        this.insertQueue = [];
        this.deleteQueue = [];
        this.isProcessingInsert = false;
        this.isProcessingDelete = false;
        this.enqueueMutex = new Mutex();  // 入队锁
        this.dequeueMutex = new Mutex();  // 出队锁
        this.ndsTasks = new Map();  // Map<ndsId, Set<taskId>>
        this.dataMutex = new Mutex();  // 用于数据操作的互斥
        
        // 配置项
        this.cleanupInterval = 120;  // 清理间隔时间（秒）
        this.dispatchInterval = 180; // 分发任务间隔时间（秒）
        
        // 任务分发状态
        this.isDispatching = false;
        this.dispatchMutex = new Mutex();  // 分发任务锁

        console.log("NDSFileList IDQueueTask init...")
        // 启动三个处理线程
        this.startInsertProcessing();
        console.log("NDSFileList InsertProcess Running.")
        this.startDeleteProcessing();
        this.startCleanupProcessing();  // 新增清理线程
        console.log("NDSFileList DeleteProcess Running.")
        
        // 启动任务分发循环
        this.startDispatchLoop();
    }

    // 检查 NDS 是否有正在处理的任务
    hasNDSTasks(ndsId) {
        return this.ndsTasks.has(ndsId) && this.ndsTasks.get(ndsId).size > 0;
    }

    // 记录任务ID到对应的NDS
    _recordTaskIds(operation) {
        const ndsIds = new Set(operation.data.files.map(file => file.NDSID));
        for (const ndsId of ndsIds) {
            if (!this.ndsTasks.has(ndsId)) {
                this.ndsTasks.set(ndsId, new Set());
            }
            this.ndsTasks.get(ndsId).add(operation.taskId);
        }
    }

    // 清理任务ID
    _cleanupTaskIds(operation) {
        const ndsIds = new Set(operation.data.files.map(file => file.NDSID));
        for (const ndsId of ndsIds) {
            if (this.ndsTasks.has(ndsId)) {
                this.ndsTasks.get(ndsId).delete(operation.taskId);
                if (this.ndsTasks.get(ndsId).size === 0) {
                    this.ndsTasks.delete(ndsId);
                }
            }
        }
    }

    async enqueue(operation) {
        const release = await this.enqueueMutex.acquire();
        try {
            const isInsert = operation.type === 'INSERT';
            const queue = isInsert ? this.insertQueue : this.deleteQueue;
            const isProcessing = isInsert ? this.isProcessingInsert : this.isProcessingDelete;
            const startProcessing = isInsert ? this.startInsertProcessing : this.startDeleteProcessing;

            queue.push(operation);
            if (isInsert) {
                this._recordTaskIds(operation);
            }
            
            if (!isProcessing) {
                // noinspection ES6MissingAwait
                startProcessing.call(this);
            }
        } finally {
            release();
        }
    }

    async startInsertProcessing() {
        if (this.isProcessingInsert) return;
        this.isProcessingInsert = true;

        while (true) {
            const operation = await this.dequeueInsert();
            if (!operation) {
                this.isProcessingInsert = false;
                break;
            }

            try {
                await this.processOperation(operation);
            } catch (error) {
                console.error('Error processing insert operation:', error);
            }
        }
    }

    async startDeleteProcessing() {
        if (this.isProcessingDelete) return;
        this.isProcessingDelete = true;

        while (true) {
            const operation = await this.dequeueDelete();
            if (!operation) {
                this.isProcessingDelete = false;
                break;
            }

            try {
                await this.processOperation(operation);
            } catch (error) {
                console.error('Error processing delete operation:', error);
            }
        }
    }

    async dequeueInsert() {
        const release = await this.dequeueMutex.acquire();
        try {
            return this.insertQueue.shift();
        } finally {
            release();
        }
    }

    async dequeueDelete() {
        const release = await this.dequeueMutex.acquire();
        try {
            return this.deleteQueue.shift();
        } finally {
            release();
        }
    }

    async processOperation(operation) {
            let transaction;
            try {
                // noinspection JSUnresolvedReference
                let options = {
                    isolationLevel: Sequelize.Transaction.ISOLATION_LEVELS.READ_COMMITTED,
                    timeout: 60000
                }
                transaction = await sequelize.transaction(options);

                switch (operation.type) {
                    case 'INSERT':
                        await this.handleInsert(operation.data, transaction);
                        break;
                    case 'DELETE':
                        await this.handleDelete(operation.data, transaction);
                        break;
                    default:
                    console.error('Unknown operation type:', operation.type);
                }

                await transaction.commit();
                // 触发dispatchParseTask
                this.dispatchParseTask();
                
            } catch (error) {
                if (transaction) {
                    try {
                        await transaction.rollback();
                    } catch (rollbackError) {
                        console.error('Rollback failed:', rollbackError);
                    }
                }
            console.error('Operation failed:', error);
        } finally {
            if (operation.type === 'INSERT') {
                this._cleanupTaskIds(operation);
            }
        }
    }

    async handleInsert(data, transaction) {
        const { files } = data;
        
        try {
            // 1. 创建临时表
            await sequelize.query(`
                CREATE TEMPORARY TABLE IF NOT EXISTS temp_nds_files (
                    FileHash VARCHAR(32) NOT NULL,
                    NDSID INT NOT NULL,
                    FilePath VARCHAR(250) NOT NULL,
                    FileTime DATETIME,
                    DataType VARCHAR(50),
                    eNodeBID VARCHAR(20),
                    SubFileName VARCHAR(250),
                    HeaderOffset BIGINT,
                    CompressSize BIGINT,
                    FileSize BIGINT,
                    FlagBits INT,
                    CompressType INT,
                    Parsed TINYINT DEFAULT 0,
                    CreateTime DATETIME,
                    UpdateTime DATETIME,
                    INDEX (FileHash)
                )
            `, { transaction });

            // 2. 分批插入到临时表
            const batchSize = 100;
            const now = new Date();
            
            for (let i = 0; i < files.length; i += batchSize) {
                const batch = files.slice(i, i + batchSize);
                await sequelize.query(`
                    INSERT INTO temp_nds_files (
                        FileHash, NDSID, FilePath, FileTime, DataType, 
                        eNodeBID, SubFileName, HeaderOffset, CompressSize, 
                        FileSize, FlagBits, CompressType, Parsed, 
                        CreateTime, UpdateTime
                    ) VALUES ${
                        batch.map(file => `(
                            ${sequelize.escape(
                                crypto.createHash('md5')
                                    .update(`${file.NDSID}_${file.FilePath}_${file.DataType}_${file.SubFileName}`)
                                    .digest('hex')
                            )},
                            ${file.NDSID},
                            ${sequelize.escape(file.FilePath)},
                            ${sequelize.escape(file.FileTime)},
                            ${sequelize.escape(file.DataType)},
                            ${sequelize.escape(file.eNodeBID)},
                            ${sequelize.escape(file.SubFileName)},
                            ${file.HeaderOffset},
                            ${file.CompressSize},
                            ${file.FileSize},
                            ${file.FlagBits},
                            ${file.CompressType},
                            ${file.Parsed || 0},
                            ${sequelize.escape(now)},
                            ${sequelize.escape(now)}
                        )`).join(',')
                    }
                `, { transaction });
            }

            // 3. 从临时表插入到正式表，忽略重复记录
            const result = await sequelize.query(`
                INSERT IGNORE INTO NDSFileList (
                    FileHash, NDSID, FilePath, FileTime, DataType,
                    eNodeBID, SubFileName, HeaderOffset, CompressSize,
                    FileSize, FlagBits, CompressType, Parsed,
                    CreateTime, UpdateTime
                )
                SELECT 
                    FileHash, NDSID, FilePath, FileTime, DataType,
                    eNodeBID, SubFileName, HeaderOffset, CompressSize,
                    FileSize, FlagBits, CompressType, Parsed,
                    CreateTime, UpdateTime
                FROM temp_nds_files
            `, { transaction });

            // 4. 删除临时表
            await sequelize.query('DROP TEMPORARY TABLE IF EXISTS temp_nds_files', { transaction });

            return result;
        } catch (error) {
            // 确保清理临时表
            try {
                await sequelize.query('DROP TEMPORARY TABLE IF EXISTS temp_nds_files', { transaction });
            } catch (cleanupError) {
                console.error('Failed to cleanup temporary table:', cleanupError);
            }
            throw error;
        }
    }

    async handleDelete(data, transaction) {
        const { files } = data;
        const batchSize = 100;
        
        for (let i = 0; i < files.length; i += batchSize) {
            const batch = files.slice(i, i + batchSize);
            await NDSFileList.update(
                { Parsed: -1 },
                {
                    where: {
                        [Op.and]: [
                            {
                                [Op.or]: batch.map(file => ({
                                    NDSID: file.NDSID,
                                    FilePath: file.FilePath
                                }))
                            },
                            {
                                Parsed: {
                                    [Op.ne]: 1 // 未正在解释的由ParserNode进行更新
                                }
                            }
                        ]
                    },
                    transaction
                }
            );
        }
    }

    // 新增清理处理方法
    async startCleanupProcessing() {
        // noinspection InfiniteLoopJS
        while (true) {
            try {
                const release = await this.dataMutex.acquire();
                try {
                    // noinspection JSUnresolvedReference
                    const transaction = await sequelize.transaction({
                        isolationLevel: Sequelize.Transaction.ISOLATION_LEVELS.READ_COMMITTED
                    });

                    try {
                        await sequelize.query(`
                            DELETE FROM NDSFileList 
                            WHERE Parsed = -1
                        `, { transaction });

                        await transaction.commit();
                    } catch (error) {
                        await transaction.rollback();
                        console.error('Error during cleanup:', error);
                    }
                } finally {
                    release();
                }
            } catch (error) {
                console.error('Error in cleanup processing:', error);
            }

            // 使用配置的清理间隔时间（秒转毫秒）
            await new Promise(resolve => setTimeout(resolve, this.cleanupInterval * 1000));
        }
    }

    // 启动定时分发循环
    async startDispatchLoop() {
        while (true) {
            await this.dispatchParseTask();
            await new Promise(resolve => setTimeout(resolve, this.dispatchInterval * 1000));
        }
    }

    // 分发Parse任务
    async dispatchParseTask() {
        const release = await this.dispatchMutex.acquire();
        
        try {
            if (this.isDispatching) {
                release();
                return;
            }
            
            this.isDispatching = true;
            
            // 1. 获取所有在线的ParserNode
            const parserNodes = await NodeList.findAll({
                where: {
                    NodeType: 'ParserNode',
                    Status: 'Online'
                }
            });

            if (!parserNodes || parserNodes.length === 0) return;

            // 2. 获取节点状态
            const nodeStatuses = await Promise.all(
                parserNodes.map(async node => {
                    try {
                        const response = await axios.get(`http://${node.Host}:${node.Port}/status`);
                        if (response.data.code === 200 && response.data.data) {
                            return { 
                                node, 
                                status: response.data.data,
                                availableProcesses: response.data.data.available_processes
                            };
                        }
                    } catch (error) {
                        // 节点通信失败，更新状态为离线
                        await NodeList.update(
                            { Status: 'Offline' },
                            { where: { ID: node.ID } }
                        );
                        return null;
                    }
                })
            );

            const availableNodes = nodeStatuses.filter(ns => ns !== null && ns.availableProcesses > 0);
            if (availableNodes.length === 0) return;

            // 3. 计算总可用进程数并获取任务
            const totalAvailableProcesses = availableNodes.reduce((sum, ns) => sum + ns.availableProcesses, 0);
            const files = await EnbFileList.findAll({limit: totalAvailableProcesses});

            if (!files || files.length === 0) return;

            // 4. 分发任务到各节点
            let fileIndex = 0;
            for (const nodeStatus of availableNodes) {
                if (fileIndex >= files.length) break;  // 如果没有更多任务了，直接退出

                const { node, availableProcesses } = nodeStatus;
                const nodeTasks = [];
                
                // 收集该节点可处理的任务
                for (let i = 0; i < availableProcesses && fileIndex < files.length; i++) {
                    nodeTasks.push(files[fileIndex++]);
                }

                if (nodeTasks.length === 0) continue;

                try {
                    // 批量更新文件状态
                    await NDSFileList.update(
                        { Parsed: 1, UpdateTime: new Date() },
                        {
                            where: {
                                FileHash: {
                                    [Op.in]: nodeTasks.map(task => task.FileHash)
                                }
                            }
                        }
                    );

                    // 批量发送任务
                    await axios.post(`http://${node.Host}:${node.Port}/task`, {
                        tasks: nodeTasks.map(file => ({
                            FileHash: file.FileHash,
                            NDSID: file.NDSID,
                            FilePath: file.FilePath,
                            FileTime: file.FileTime.toISOString(), // 确保日期格式统一
                            DataType: file.DataType,
                            eNodeBID: parseInt(file.eNodeBID), // 确保数字类型
                            SubFileName: file.SubFileName,
                            HeaderOffset: parseInt(file.HeaderOffset),
                            CompressSize: parseInt(file.CompressSize),
                            FileSize: file.FileSize ? parseInt(file.FileSize) : null,
                            FlagBits: file.FlagBits ? parseInt(file.FlagBits) : null,
                            CompressType: file.CompressType ? parseInt(file.CompressType) : null
                        }))
                    });
                } catch (error) {
                    // 发送失败，将节点标记为离线并恢复文件状态
                    await NodeList.update(
                        { Status: 'Offline' },
                        { where: { ID: node.ID } }
                    );
                    
                    await NDSFileList.update(
                        { Parsed: 0, UpdateTime: new Date() },
                        {
                            where: {
                                FileHash: {
                                    [Op.in]: nodeTasks.map(task => task.FileHash)
                                }
                            }
                        }
                    );
                }
            }
        } catch (error) {
            return;
        } finally {
            this.isDispatching = false;
            release();
        }
    }
}

// 创建单例
const fileQueue = new FileOperationQueue();
module.exports = fileQueue; 