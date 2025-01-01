// noinspection JSIgnoredPromiseFromCall,JSUnresolvedReference,InfiniteLoopJS

const { Mutex } = require('async-mutex');
const { queue } = require('async');
const { sequelize, Sequelize } = require('./DataBasePool');
const NDSFileList = require('../Models/NDSFileList');
const EnbFileTasks = require('../Models/EnbFileTasks');
const { Op } = require('sequelize');
const crypto = require('crypto');

class AsyncFileOperationQueue {
    constructor() {
        // 创建插入和删除队列
        this.insertQueue = queue(async (operation, callback) => {
            try {
                let transaction = await sequelize.transaction({
                    isolationLevel: Sequelize.Transaction.ISOLATION_LEVELS.READ_COMMITTED
                });

                try {
                    await this.handleInsert(operation.data, transaction);
                    await transaction.commit();
                    await taskQueue.checkAndReplenish();
                    callback(null);
                } catch (error) {
                    await transaction.rollback();
                    callback(error);
                }
            } catch (error) {
                callback(error);
            }
        }, 1);

        this.deleteQueue = queue(async (operation, callback) => {
            try {
                let transaction = await sequelize.transaction({
                    isolationLevel: Sequelize.Transaction.ISOLATION_LEVELS.READ_COMMITTED
                });

                try {
                    await this.handleDelete(operation.data, transaction);
                    await transaction.commit();
                    callback(null);
                } catch (error) {
                    await transaction.rollback();
                    callback(error);
                }
            } catch (error) {
                callback(error);
            }
        }, 1);

        this.ndsTasks = new Map();  // Map<ndsId, Set<taskId>>
        this.dataMutex = new Mutex();  // 用于数据操作的互斥

        // 启动清理进程
        this.startCleanupProcessing();
        console.log("AsyncFileOperationQueue initialized");
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

    // 入队操作
    async enqueue(operation) {
        return new Promise((resolve, reject) => {
            const queue = operation.type === 'INSERT' ? this.insertQueue : this.deleteQueue;
            
            if (operation.type === 'INSERT') {
                this._recordTaskIds(operation);
            }

            queue.push(operation, (err) => {
                if (operation.type === 'INSERT') {
                    this._cleanupTaskIds(operation);
                }
                if (err) reject(err);
                else resolve();
            });
        });
    }

    // 处理插入操作
    async handleInsert(data, transaction) {
        const { files } = data;
        try {
            // 创建临时表
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

            // 分批插入
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

            // 从临时表插入到正式表
            await sequelize.query(`
                INSERT IGNORE INTO NDSFileList (
                    FileHash, NDSID, FilePath, FileTime, DataType,
                    eNodeBID, SubFileName, HeaderOffset, CompressSize,
                    FileSize, FlagBits, CompressType, Parsed,
                    CreateTime, UpdateTime
                )
                SELECT * FROM temp_nds_files
            `, { transaction });

            // 删除临时表
            await sequelize.query('DROP TEMPORARY TABLE IF EXISTS temp_nds_files', { transaction });
        } catch (error) {
            await sequelize.query('DROP TEMPORARY TABLE IF EXISTS temp_nds_files', { transaction });
            throw error;
        }
    }

    // 处理删除操作
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
                                    [Op.ne]: 1
                                }
                            }
                        ]
                    },
                    transaction
                }
            );
        }
    }

    // 清理进程
    async startCleanupProcessing() {
        while (true) {
            try {
                const release = await this.dataMutex.acquire();
                try {
                    await NDSFileList.destroy({
                        where: { Parsed: -1 }
                    });
                } finally {
                    release();
                }
            } catch (error) {
                console.warn('Cleanup cycle error:', error.message);
            }
            await new Promise(resolve => setTimeout(resolve, 120000)); // 每2分钟清理一次
        }
    }
}


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

        console.log("NDSFileList IDQueueTask init...")
        // 启动处理线程
        this.startInsertProcessing();
        console.log("NDSFileList InsertProcess Running.")
        this.startDeleteProcessing();
        this.startCleanupProcessing();  // 新增清理线程
        console.log("NDSFileList DeleteProcess Running.")
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
                    // 在 INSERT 操作完成后检查任务队列
                    await taskQueue.checkAndReplenish();
                    break;
                case 'DELETE':
                    await this.handleDelete(operation.data, transaction);
                    break;
                default:
                    console.error('Unknown operation type:', operation.type);
                }

            await transaction.commit();
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

    async startCleanupProcessing() {
        while (true) {
            try {
                const release = await this.dataMutex.acquire();
                try {
                    // 先尝试一次性删除
                    let transaction = await sequelize.transaction({
                        isolationLevel: Sequelize.Transaction.ISOLATION_LEVELS.READ_COMMITTED
                    });

                    try {
                        await NDSFileList.destroy({
                            where: { Parsed: -1 },
                            transaction,
                            // 使用 Sequelize 的查询超时
                            lock: true,
                            timeout: 3600000 // 1小时超时
                        });

                        await transaction.commit();
                    } catch (error) {
                        await transaction.rollback();
                        // 超时后切换到分批删除模式
                        const BATCH_SIZE = 100; // 每批删除100条记录
                        while (true) {
                            try {
                                // 查找要删除的记录
                                const records = await NDSFileList.findAll({
                                    where: { Parsed: -1 },
                                    attributes: ['FileHash'],
                                    limit: BATCH_SIZE,
                                    lock: false // 不锁表
                                });

                                if (records.length === 0) break;

                                // 获取 FileHash 列表
                                const fileHashes = records.map(record => record.FileHash);

                                // 执行删除操作
                                transaction = await sequelize.transaction({
                                    isolationLevel: Sequelize.Transaction.ISOLATION_LEVELS.READ_COMMITTED
                                });

                                try {
                                    await NDSFileList.destroy({
                                        where: {
                                            FileHash: {
                                                [Op.in]: fileHashes
                                            }
                                        },
                                        transaction,
                                        timeout: 360000
                                    });

                                    await transaction.commit();
                                } catch (batchError) {
                                    await transaction.rollback();
                                    break;
                                }

                                await new Promise(resolve => setTimeout(resolve, 100));
                            } catch (findError) {
                                break;
                            }
                        }
                    }
                } finally {
                    release();
                }
            } catch (error) {
                console.warn('Cleanup cycle error:', error.message);
            }

            // 使用配置的清理间隔时间
            await new Promise(resolve => setTimeout(resolve, this.cleanupInterval * 1000));
        }
    }
}


class TaskQueue {
    constructor() {
        // 创建异步队列，并发数设为1确保顺序处理
        this.taskQueue = queue(async (task, callback) => {
            try {
                callback(null, task);
            } catch (error) {
                callback(error);
            }
        }, 1);

        this.replenishMutex = new Mutex();
        this.minQueueSize = 50;
    }

    // 补充队列
    async replenishQueue() {
        const release = await this.replenishMutex.acquire();
        try {
            const tasks = await EnbFileTasks.findAll({
                limit: 1000
            });
            
            // 将任务添加到异步队列
            for (const task of tasks) {
                this.taskQueue.push(task);
            }
        } finally {
            release();
        }
    }

    // 获取任务
    async getTask() {
        // 如果队列长度小于阈值，补充任务
        if (this.taskQueue.length() < this.minQueueSize) {
            await this.replenishQueue();
        }

        // 返回一个Promise，当有任务时会被解决
        return new Promise((resolve, reject) => {
            this.taskQueue.push((err, task) => {
                if (err) reject(err);
                else resolve(task);
            });
        });
    }

    // 检查并补充队列
    async checkAndReplenish() {
        if (this.taskQueue.length() < this.minQueueSize) {
            await this.replenishQueue();
        }
    }
}





// 创建单例
const fileQueue = new FileOperationQueue();
const taskQueue = new TaskQueue();
module.exports = { fileQueue, taskQueue };
