/*
 Navicat Premium Data Transfer

 Source Server         : localmysql
 Source Server Type    : MySQL
 Source Server Version : 80039 (8.0.39)
 Source Host           : localhost:3306
 Source Schema         : MParser

 Target Server Type    : MySQL
 Target Server Version : 80039 (8.0.39)
 File Encoding         : 65001

 Date: 16/12/2024 01:11:56
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for CellData
-- ----------------------------
DROP TABLE IF EXISTS `CellData`;
CREATE TABLE `CellData`  (
  `CGI` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `eNodeBID` int NULL DEFAULT NULL,
  `PCI` int NULL DEFAULT NULL,
  `Azimuth` int NULL DEFAULT NULL,
  `Earfcn` int NULL DEFAULT NULL,
  `Freq` double NULL DEFAULT NULL,
  `eNBName` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `userLabel` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `Longitude` double NULL DEFAULT NULL,
  `Latitude` double NULL DEFAULT NULL,
  UNIQUE INDEX `CGI`(`CGI` ASC) USING BTREE,
  INDEX `eNodeBID`(`eNodeBID` ASC) USING BTREE,
  INDEX `PCI`(`PCI` ASC) USING BTREE,
  INDEX `Earfcn`(`Earfcn` ASC) USING BTREE,
  INDEX `Freq`(`Freq` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 737648 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for Log
-- ----------------------------
DROP TABLE IF EXISTS `Log`;
CREATE TABLE `Log`  (
  `LogID` bigint NOT NULL AUTO_INCREMENT,
  `LogTime` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `LogFrom` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `LogText` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL,
  `LogType` int NULL DEFAULT NULL COMMENT '0=Info, 1=Warning/Error',
  PRIMARY KEY (`LogID`) USING BTREE,
  INDEX `LogFrom`(`LogFrom` ASC) USING BTREE,
  INDEX `LogTime`(`LogTime` ASC) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMPRESSION = 'NONE' ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for MZIPFileInfo
-- ----------------------------
DROP TABLE IF EXISTS `MZIPFileInfo`;
CREATE TABLE `MZIPFileInfo`  (
  `ID` bigint NOT NULL AUTO_INCREMENT,
  `FileID` bigint NOT NULL,
  `NDSID` int NOT NULL,
  `eNodeBID` int NOT NULL,
  `DataType` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `FileTime` datetime NULL DEFAULT NULL,
  `FilePath` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `SubFileName` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `HeaderOffset` bigint NOT NULL,
  `CompressSize` bigint NOT NULL,
  `FileSize` bigint NULL DEFAULT NULL,
  `FlaggBits` int NULL DEFAULT NULL,
  `CompressType` int NULL DEFAULT NULL,
  `Parsed` int NOT NULL DEFAULT 0,
  PRIMARY KEY (`ID`) USING BTREE,
  UNIQUE INDEX `Lock`(`FileID` ASC, `SubFileName` ASC) USING BTREE COMMENT '用于防止重复提交，并且可配合NDSFileList的Lock组成过时锁',
  INDEX `ID`(`ID` ASC) USING BTREE,
  INDEX `FileID`(`FileID` ASC) USING BTREE,
  INDEX `NDSID`(`NDSID` ASC) USING BTREE,
  INDEX `DataType`(`DataType` ASC) USING BTREE,
  INDEX `FileTime`(`FileTime` ASC) USING BTREE,
  INDEX `Parsed`(`Parsed` ASC) USING BTREE,
  INDEX `eNodeBID`(`eNodeBID` ASC) USING BTREE,
  INDEX `MEDF`(`eNodeBID` ASC, `DataType` ASC, `FileTime` ASC) USING BTREE COMMENT '用于快速查询各个enb在NDS中有效数据的时间范围',
  CONSTRAINT `FollowNDSFileListFileID` FOREIGN KEY (`FileID`) REFERENCES `NDSFileList` (`ID`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1001 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for NDSFileList
-- ----------------------------
DROP TABLE IF EXISTS `NDSFileList`;
CREATE TABLE `NDSFileList`  (
  `ID` bigint NOT NULL AUTO_INCREMENT,
  `NDSID` int NULL DEFAULT NULL,
  `DataType` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL COMMENT 'MDT/MRO',
  `FilePath` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `FileTime` datetime NOT NULL,
  `AddTime` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `Parsed` int NULL DEFAULT 0,
  `LockTime` datetime NULL DEFAULT NULL,
  `TaskUUID` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  PRIMARY KEY (`ID`) USING BTREE,
  UNIQUE INDEX `NDSFile`(`NDSID` ASC, `FilePath` ASC) USING BTREE,
  INDEX `ID`(`ID` ASC) USING BTREE,
  INDEX `Parsed`(`Parsed` ASC) USING BTREE,
  INDEX `NDSID`(`NDSID` ASC, `DataType` ASC, `FilePath` ASC) USING BTREE,
  INDEX `LockTime`(`LockTime` ASC) USING BTREE,
  INDEX `TaskUUID`(`TaskUUID` ASC) USING BTREE,
  CONSTRAINT `FollowNDSList` FOREIGN KEY (`NDSID`) REFERENCES `NDSList` (`ID`) ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE = InnoDB AUTO_INCREMENT = 1000 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- Table structure for NDSList
-- ----------------------------
DROP TABLE IF EXISTS `NDSList`;
CREATE TABLE `NDSList`  (
  `ID` int NOT NULL AUTO_INCREMENT,
  `NDSName` varchar(150) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `Address` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `Port` int NULL DEFAULT NULL,
  `Protocol` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL,
  `Account` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `Password` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `MRO_Path` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `MRO_Filter` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `MDT_Path` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `MDT_Filter` varchar(250) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL,
  `Status` int NOT NULL DEFAULT 1,
  `Switch` int NOT NULL DEFAULT 1,
  `AddTime` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`ID`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 34 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci ROW_FORMAT = DYNAMIC;

-- ----------------------------
-- View structure for enbtime
-- ----------------------------
DROP VIEW IF EXISTS `enbtime`;
CREATE ALGORITHM = UNDEFINED SQL SECURITY DEFINER VIEW `enbtime` AS select `mzipfileinfo`.`eNodeBID` AS `eNodeBID`,`mzipfileinfo`.`DataType` AS `DataType`,min(`mzipfileinfo`.`FileTime`) AS `MinTime`,max(`mzipfileinfo`.`FileTime`) AS `MaxTime` from `mzipfileinfo` group by `mzipfileinfo`.`eNodeBID`,`mzipfileinfo`.`DataType`;

-- ----------------------------
-- Procedure structure for GetNDSUNParseFiles
-- ----------------------------
DROP PROCEDURE IF EXISTS `GetNDSUNParseFiles`;
delimiter ;;
CREATE PROCEDURE `GetNDSUNParseFiles`(`nds_id` int,`max_rn` int)
BEGIN
	DECLARE TaskID VARCHAR(64);
	START TRANSACTION;
	-- 解锁超时任务，重回任务池
	UPDATE NDSFileList SET LockTime = NULL, TaskUUID = NULL WHERE NDSID = `nds_id` AND LockTime IS NOT NULL AND TIMESTAMPDIFF(MINUTE,LockTime,NOW()) > 30;
	-- 查询未解析任务并锁定
	SET TaskID = UUID();
	UPDATE NDSFileList SET LockTime = NOW(), TaskUUID = TaskID WHERE id IN (
		SELECT id FROM (
			SELECT id,FileTime, NDSID, rn FROM (
				SELECT *, ROW_NUMBER() OVER (PARTITION BY NDSID ORDER BY FileTime) AS rn FROM NDSFileList WHERE NDSID = `nds_id` AND Parsed = 0 AND LockTime IS NULL
			) AS RankedFiles 
			WHERE rn <=`max_rn` ORDER BY FileTime, NDSID
		) AS IDS
	);
	COMMIT;
	SELECT * FROM NDSFileList WHERE TaskUUID = TaskID;
END
;;
delimiter ;

SET FOREIGN_KEY_CHECKS = 1;
