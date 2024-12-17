import os
import re
import stat
import aioftp
import struct
import asyncssh
from io import BytesIO
from datetime import datetime
from Utils import KeyType, is_regex
from ErrorException import ScanError


class NDSClient:
    def __init__(self, protocol, host, port, user, passwd):
        self.protocol = protocol
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd
        self.__ftp = None
        self.__sftp = None
        self.client = None
        self.__stream = None
        self.stream_path = None
        self.stream_info = {}
        self.__stream_offset = 0

    async def connect(self):
        if self.protocol == "FTP":
            self.__ftp = aioftp.Client()
            await self.__ftp.connect(self.host, self.port)
            await self.__ftp.login(self.user, self.passwd)
            self.client = self.__ftp

        elif self.protocol == "SFTP":
            self.__sftp = await asyncssh.connect(host=self.host, port=self.port, username=self.user,
                                                 password=self.passwd, known_hosts=None)
            self.client = await self.__sftp.start_sftp_client()
        else:
            raise ScanError("Invalid protocol, only support FTP and SFTP", "NDSClient.connect", 1)

    async def check_connect(self):
        try:
            if self.client is None:
                return False
            if self.protocol == "FTP":
                try:
                    await self.client.change_directory("/")
                except aioftp.StatusCodeError as e:
                    if e.received_codes == [250]:
                        return True
                    else:
                        raise
            elif self.protocol == "SFTP":
                await self.client.lsdir("/")
            else:
                return False
            return True
        except:
            return False

    async def close_connect(self):
        try:
            if self.protocol == "FTP":
                await self.__ftp.quit()
            elif self.protocol == "SFTP":
                await self.__sftp.close()
        except Exception as e:
            raise e
        finally:
            self.client = None
            self.__ftp = None
            self.__sftp = None

    async def scan(self, scan_path, filter_pattern=None):
        files = []
        use_filter = True if filter_pattern and is_regex(filter_pattern) else False
        if filter_pattern and not use_filter:
            raise ScanError("Scanner filter error", level=1)

        if self.client is None:
            raise ScanError("Not init NDS Client", "NDSClient.scan", -1)
        if self.protocol == "FTP":
            async for path, info in self.client.list(scan_path, recursive=True):
                if info.get('type') == 'file':
                    if use_filter:
                        if re.search(filter_pattern, str(path)):
                            files.append(str(path))
                    else:
                        files.append(str(path))

        elif self.protocol == "SFTP":
            #  使用队列方式代替函数递归
            stack = [scan_path]
            while stack:
                current_path = stack.pop()
                async for entry in self.client.scandir(current_path):
                    full_path = f"{current_path.rstrip('/')}/{entry.filename}"
                    if stat.S_ISDIR(entry.attrs.permissions):
                        stack.append(full_path)
                    else:
                        if use_filter:
                            if re.search(filter_pattern, str(full_path)):
                                files.append(str(full_path))
                        else:
                            files.append(str(full_path))
        else:
            raise ScanError("Invalid protocol, only support FTP and SFTP", "NDSClient.scan", 1)
        return files

    async def file_exists(self, remote_path):
        try:
            await self.client.stat(remote_path)
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            raise ScanError(str(e), "NDSClient.file_exists", 1)

    async def stat(self, file_path):
        if not await self.file_exists(file_path):
            return None
        info_obj = await self.client.stat(file_path)
        if not info_obj:
            return None

        if self.protocol == "FTP":
            info = info_obj
            modify = info.get('modify')
            modify = datetime(
                int(modify[:4]), int(modify[4:6]), int(modify[6:8]),
                int(modify[8:10]), int(modify[10:12]), int(modify[12:14]), 0
            ).strftime('%Y-%m-%d %H:%M:%S') if modify else modify
        elif self.protocol == "SFTP":
            info = {attr: getattr(info_obj, attr, None) for attr in dir(info_obj) if not attr.startswith('_')}
            modify = info.get('modify')
            modify = datetime.fromtimestamp(modify).strftime('%Y-%m-%d %H:%M:%S') if modify else modify
        else:
            return None

        self.stream_info = {
            "file_path": file_path,
            "directory": file_path.rsplit('/', 1)[0],
            "filename": file_path.rsplit('/', 1)[1],
            "size": int(info.get('size')),
            "modify": modify
        }
        return self.stream_info

    async def open(self, file_path):
        self.stream_info = await self.stat(file_path)
        if not self.stream_info:
            self.stream_path = None
            raise ScanError("remote file is not exists", "NDSClient.open", 1)
        if self.protocol == "SFTP":
            self.__stream = await self.client.open(file_path, 'rb')
        self.stream_path = file_path

    def seek(self, offset=0, whence=0):
        self.__stream_offset = (
            self.stream_info['size'] - abs(
                offset) if whence == 2 else self.__stream_offset + offset if whence == 1 else offset
        )

    async def read(self, size=None):
        if self.client is None:
            raise ScanError("Not init NDS Client", "NDSClient.read", -1)
        if self.stream_path is None:
            raise ScanError("File is not open", "NDSClient.read", 0)
        if self.protocol == "FTP":
            try:
                stream = await self.client.get_stream("RETR " + self.stream_path, "1xx", offset=self.__stream_offset)
                tmp_io = BytesIO()
                size = size if size and self.__stream_offset + size <= self.stream_info['size'] else \
                    self.stream_info['size'] - self.__stream_offset
                total = size
                offset = self.__stream_offset
                while total > 0:
                    block = await stream.read(min(abs(total), 2048))
                    if not block:
                        break
                    tmp_io.write(block)
                    total -= len(block)
                    offset += len(block)
                    if size and tmp_io.tell() >= size:
                        await stream.finish('xxx')
                        break
                self.__stream_offset = self.__stream_offset + size if size else self.stream_info["size"]
                return tmp_io.getvalue()[0:size]
            except Exception as e:
                raise ScanError(f'read warning: {e}', "NDSClient.read", -1)
        elif self.protocol == "SFTP":
            if self.__stream is None:
                raise ScanError("File is not open", "NDSClient.read", 1)
            try:
                size = size if size and self.__stream_offset + size <= self.stream_info['size'] else \
                    self.stream_info['size'] - self.__stream_offset
                data = await self.__stream.read(size, self.__stream_offset)
                self.__stream_offset = self.__stream_offset + size if size else self.stream_info['size']
            except Exception as e:
                raise ScanError(f'read warning: {e}', "NDSClient.read", -1)
            return data
        else:
            raise ScanError("Invalid protocol, only support FTP and SFTP", "NDSClient.read", 1)

    async def get_zip_info(self):
        # 读取文件头
        header_str = b"PK\003\004"  # ZIP文件的魔术数字
        header_struct = "<4s2B4HL2L2H"  # ZIP文件的本地文件头格式
        header_size = struct.calcsize(header_struct)
        self.seek(0, 0)
        tmp_data = await self.read(header_size)
        header_data = struct.unpack(header_struct, tmp_data)
        if len(tmp_data) != header_size or header_data[0] != header_str:
            raise Exception("ZIP header warning")
        self.stream_info['header_size'] = header_data[10] + header_data[11] + header_size
        # 解析中央目录结构
        cd_end_struct = b"<4s4H2LH"  # structEndArchive
        cd_end_str = b"PK\005\006"  # stringEndArchive
        cd_end_size = struct.calcsize(cd_end_struct)  # sizeEndCentDir
        self.seek(cd_end_size, 2)
        tmp_data = await self.read()
        if len(tmp_data) != cd_end_size or tmp_data[0:4] != cd_end_str or tmp_data[-2:] != b"\000\000":
            raise Exception("ZIP CentDirectory warning")  # 要么不是ZIP文件，要么带了注释，暂时不解决注释问题
        cd_rec = struct.unpack(cd_end_struct, tmp_data)
        cd_rec = list(cd_rec)
        cd_rec.append(b"")
        cd_rec.append(self.stream_info['size'] - cd_end_size)
        # 尝试读取ZIP64中央目录文件(用于兼容ZIP64)
        cd_end_64_struct = "<4sQ2H2L4Q"  # structEndArchive64
        cd_end_64_str = b"PK\x06\x06"  # stringEndArchive64
        cd_end_64_size = struct.calcsize(cd_end_64_struct)  # sizeEndCentDir64
        cd_end_l64_struct = "<4sLQL"  # structEndArchive64Locator
        cd_end_l64_str = b"PK\x06\x07"  # stringEndArchive64Locator
        cd_end_l64_size = struct.calcsize(cd_end_l64_struct)  # sizeEndCentDir64Locator
        if cd_end_size + cd_end_l64_size < self.stream_info['size']:
            self.seek(-cd_end_size - cd_end_l64_size, 2)
            tmp_data = await self.read(cd_end_l64_size)
            if len(tmp_data) == cd_end_l64_str:
                sig, disk_no, rel_off, disks = struct.unpack(cd_end_l64_struct, tmp_data)
                if sig == cd_end_l64_str:
                    if disk_no != 0 or disks > 1:
                        raise Exception("ZIP Files that span multiple disks are not supported")
                    # Assume no 'zip64 extensible data'
                    self.seek(-cd_end_64_size - cd_end_l64_size - cd_end_64_size, 2)
                    if len(tmp_data) == cd_end_64_size:
                        sig, sz, create_version, read_version, disk_num, disk_dir, \
                            dir_count, dir_count2, dir_size, dir_offset = \
                            struct.unpack(cd_end_64_struct, tmp_data)
                        if sig == cd_end_64_str:
                            # 更新为ZIP64中央目录结构
                            cd_rec[0:7] = [sig, disk_num, disk_dir, dir_count, dir_count2, dir_size, dir_offset]
                            # cd_rec[0] = sig  # _ECD_SIGNATURE
                            # cd_rec[1] = disk_num  # _ECD_DISK_NUMBER
                            # cd_rec[2] = disk_dir  # _ECD_DISK_START
                            # cd_rec[3] = dir_count  # _ECD_ENTRIES_THIS_DISK
                            # cd_rec[4] = dir_count2  # _ECD_ENTRIES_TOTAL
                            # cd_rec[5] = dir_size  # _ECD_SIZE
                            # cd_rec[6] = dir_offset  # _ECD_OFFSET
        cd_end_size = cd_rec[5]  # _ECD_SIZE 中央目录字节尺寸
        cd_offset = cd_rec[6]  # _ECD_OFFSET 中央目录开始位置
        concat = cd_rec[9] - cd_end_size - cd_offset  # _ECD_LOCATION = 9
        concat -= (cd_end_64_size + cd_end_l64_size) if cd_rec[0] == cd_end_64_str else 0  # ZIP64扩展结构
        offset = cd_offset + concat
        self.seek(offset, 0)
        tmp_data = await self.read(cd_end_size)
        data = BytesIO(tmp_data)
        cd_dir_struct = "<4s4B4HL2L5H2L"  # structCentralDir
        cd_dir_str = b"PK\001\002"  # stringCentralDir
        cd_dir_size = struct.calcsize(cd_dir_struct)  # sizeCentralDir
        total = 0
        file_info_array = []
        while total < cd_end_size:
            centdir = data.read(cd_dir_size)
            if len(centdir) != cd_dir_size:
                raise Exception("Truncated central directory")
            centdir = struct.unpack(cd_dir_struct, centdir)
            if centdir[0] != cd_dir_str:  # _CD_SIGNATURE = 0
                raise Exception("Bad magic number for central directory")
            if centdir[3] > 63:  # centdir[3]: extract_version, MAX_EXTRACT_VERSION = 63, 目前支持6.3及以下版本的ZIP包
                raise Exception("zip file version %.1f" % (centdir[3] / 10))

            info = KeyType()
            info.directory, info.file_name = os.path.split(self.stream_path)
            info.sub_file_name = data.read(centdir[12])  # _CD_FILENAME_LENGTH = 12
            flags = centdir[5]  # _CD_FLAG_BITS = 5
            # _MASK_UTF_FILENAME = 1 << 11 = 2048
            info.sub_file_name = info.sub_file_name.decode('utf-8') if flags & 2048 else info.sub_file_name.decode(
                'cp437')
            # _CD_LOCAL_HEADER_OFFSET 文件开始位置，需要加上文件头尺寸
            info.header_offset = centdir[18] + self.stream_info['header_size']
            info.compress_size = centdir[10]
            info.file_size = centdir[11]
            info.flag_bits = centdir[5]
            info.compress_type = centdir[6]

            #  定制化处理，MRO/MDT eNB ID提取
            match = re.search(r"_(\d{6,8})_", info.sub_file_name)
            if match:
                info.enodebid = match.group(1)
                file_info_array.append(info)
            #  使用read跳过部分无需读取的数据信息
            # _CD_EXTRA_FIELD_LENGTH = 13 // 额外字段信息
            # _CD_COMMENT_LENGTH = 14 // 注释
            data.seek(centdir[13] + centdir[14], 1)
            total = total + cd_dir_size + centdir[12] + centdir[13] + centdir[14]
        return file_info_array
