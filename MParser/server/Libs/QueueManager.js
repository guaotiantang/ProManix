// noinspection JSIgnoredPromiseFromCall

const { Mutex } = require('async-mutex');
const { sequelize, Sequelize } = require('./DataBasePool');
const NDSFileList = require('../Models/NDSFileList');
const { Op } = require('sequelize');
const crypto = require('crypto');

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

        console.log("NDSFileList IDQueueTask init...")
        // 启动三个处理线程
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
                        [Op.or]: batch.map(file => ({
                            NDSID: file.NDSID,
                            FilePath: file.FilePath
                        }))
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

            await new Promise(resolve => setTimeout(resolve, 3 * 60 * 1000));
        }
    }
}

// 创建单例
const fileQueue = new FileOperationQueue();
module.exports = fileQueue; 