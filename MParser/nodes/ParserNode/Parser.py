import pandas as pd
from io import BytesIO
from lxml import etree
from typing import Dict, List, Union


class ParseError(Exception):
    """自定义异常类用于解析错误"""

    def __init__(self, data_type, message, error_type="UnknownError"):
        super().__init__(message)
        self.data_type = data_type
        self.error_type = error_type
        self.message = message

    def __str__(self):
        return f"Parser({self.data_type})[{self.error_type}] {self.message}"


# noinspection PyPep8Naming
def mro(data: BytesIO | bytes) -> List[List[Dict[str, Union[pd.Timestamp, int, float]]]]:
    """解析MRO - XML格式数据

    Args:
        data (BytesIO | bytes): MRO数据 (字节|数据流)

    Returns:
        List[List[Dict[str, Union[pd.Timestamp, int, float]]]]: 解析后的数据列表，格式如下：
        [
            [  # 符合MRO数据字段格式的每个measurement的数据
                {   # 每条记录的字段
                    'DataTime': pd.Timestamp,          # 数据时间
                    'MR_LteScENBID': int,             # 服务小区基站ID
                    'MR_LteScEarfcn': int,            # 服务小区频点
                    'MR_LteScPci': int,               # 服务小区PCI
                    'MR_LteScSPCount': int,           # 服务小区采样点数
                    'MR_LteScRSRPAvg': float,         # 服务小区RSRP平均值
                    'MR_LteNcEarfcn': int,            # 邻区频点
                    'MR_LteNcPci': int,               # 邻区PCI
                    'MR_LteNcSPCount': int,           # 邻区采样点数
                    'MR_LteNcRSRPAvg': float,         # 邻区RSRP平均值
                    'MR_LteCC6Count': int,            # 同频6db采样点数
                    'MR_LteMOD3Count': int            # MOD3采样点数
                },
                ...  # 更多记录
            ],
            ...  # 更多measurement数据
        ]

    Raises:
        ParseError: 解析错误，包含以下类型：
            - DataError: 无法获取MRO时间(15分钟粒度时间)
            - XMLSyntaxError: XML语法错误
            - TypeError: 不支持的数据类型
            - UnexpectedError: 其他未知错误
    """
    try:
        result = []

        # 定义需要检查的字段
        smr_check = {
            "MR_LteScEarfcn", "MR_LteScPci", "MR_LteScRSRP",
            "MR_LteNcEarfcn", "MR_LteNcPci", "MR_LteNcRSRP"
        }

        if isinstance(data, bytes):
            tree = etree.fromstring(data)
        elif isinstance(data, BytesIO):
            tree = etree.parse(data).getroot()
        else:
            raise ParseError(data_type="MRO", error_type="TypeError", message="Unsupported data type for parsing")
        LteScENBID = tree.find('.//eNB').attrib['id']  # 提取eNodeBID
        file_header = tree.find('.//fileHeader')
        if file_header is not None:
            start_time = file_header.get('startTime')
            data_time = pd.to_datetime(start_time)
        else:
            raise ParseError(data_type="MRO", error_type="DataError", message="Missing startTime in fileHeader")
        for measurement in tree.findall('.//measurement'):
            smr_content = measurement.find('smr').text.strip()
            smr_content = smr_content.replace('MR.', 'MR_')
            smr_fields = smr_content.split()
            data = []

            if not smr_check.issubset(set(smr_fields)):
                continue  # 检查必要字段是否存在，当不存在时跳过该measurement节点

            headers = ["MR_LteScENBID"] + list(smr_check)  # 字段列表(添加MR_LteScENBID)
            smr_values = {x: i for i, x in enumerate(smr_fields) if x in smr_check}  # 字段索引映射
            max_field_num = smr_values[max(smr_values, key=smr_values.get)]  # 找出所需字段中最后的索引位置
            for obj in measurement.findall('object'):  # 遍历每个measurement下的object元素
                for v in obj.findall('v'):  # 遍历每个object下的v元素（<v></v>）
                    values = v.text.strip().split()  # 分割v元素内的文本内容
                    if len(values) >= max_field_num:  # 如果值的数量不够，跳过这条记录
                        # 构建一行数据：[LteScENBID] + [对应位置的测量值]
                        row_data = [LteScENBID] + [values[smr_values[x]] for x in headers[1:]]
                        if 'NIL' not in row_data:
                            data.append(row_data)  # 如果数据中没有NIL（无效值），则添加到数据列表中

            df = pd.DataFrame(data, columns=headers)  # 将数据转换为DataFrame
            # 将 NIL 转换为 NaN
            for col in smr_check:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # 进行类型转换
            df = df.astype({
                'MR_LteScENBID': 'int32',
                'MR_LteScEarfcn': 'int32',
                'MR_LteScPci': 'int32',
                'MR_LteScRSRP': 'int32',
                'MR_LteNcEarfcn': 'int32',
                'MR_LteNcPci': 'int32',
                'MR_LteNcRSRP': 'int32'
            })

            # 计算同频6db和MOD3采样点数
            df['MR_LteFCIn6db'] = (
                    (df['MR_LteScEarfcn'] == df['MR_LteNcEarfcn']) &
                    (df['MR_LteScRSRP'] - df['MR_LteNcRSRP'] <= 6)
            ).astype(int)

            # 计算MOD3采样点数
            df['MR_LTEMod3'] = (
                    (df['MR_LteScEarfcn'] == df['MR_LteNcEarfcn']) &
                    (df['MR_LteScPci'] % 3 == df['MR_LteNcPci'] % 3) &
                    (df['MR_LteScRSRP'] - df['MR_LteNcRSRP'] <= 3) &
                    (df['MR_LteScRSRP'] >= 30)
            ).astype(int)

            # 数据分组统计 - 按指定字段分组，统计每组的和以及平均值
            grouped = df.groupby(
                ["MR_LteScENBID", "MR_LteScEarfcn", "MR_LteScPci", "MR_LteNcEarfcn", "MR_LteNcPci"]
            ).agg(
                MR_LteScSPCount=pd.NamedAgg(column="MR_LteScRSRP", aggfunc='count'),
                MR_LteScRSRPAvg=pd.NamedAgg(column="MR_LteScRSRP", aggfunc=lambda x: x.mean()),
                MR_LteNcSPCount=pd.NamedAgg(column="MR_LteNcRSRP", aggfunc='count'),
                MR_LteNcRSRPAvg=pd.NamedAgg(column="MR_LteNcRSRP", aggfunc=lambda x: x.mean()),
                MR_LteCC6Count=pd.NamedAgg(column="MR_LteFCIn6db", aggfunc='sum'),
                MR_LteMOD3Count=pd.NamedAgg(column="MR_LTEMod3", aggfunc='sum')
            ).reset_index()

            # 添加DataTime时间字段(15分钟粒度文件时间)
            grouped['DataTime'] = data_time.floor('15min')

            # 类型转换，确保与数据库类型一致
            grouped['MR_LteScENBID'] = grouped['MR_LteScENBID'].astype('int32')
            grouped['MR_LteScEarfcn'] = grouped['MR_LteScEarfcn'].astype('int32')
            grouped['MR_LteScPci'] = grouped['MR_LteScPci'].astype('int32')
            grouped['MR_LteNcEarfcn'] = grouped['MR_LteNcEarfcn'].astype('int32')
            grouped['MR_LteNcPci'] = grouped['MR_LteNcPci'].astype('int32')

            result.append(grouped.to_dict('records'))  # 将处理后的数据添加到结果中
        return result
    except etree.XMLSyntaxError as e:
        raise ParseError(data_type="MRO", error_type="XMLSyntaxError", message=f"XML Syntax Error: {str(e)}")
    except ValueError as e:
        raise ParseError(data_type="MRO", error_type="ValueError", message=f"Value Error: {str(e)}")
    except KeyError as e:
        raise ParseError(data_type="MRO", error_type="KeyError", message=f"Missing Key: {str(e)}")
    except Exception as e:
        raise ParseError(data_type="MRO", error_type="UnexpectedError", message=f"Unexpected Error: {str(e)}")


def mdt(data):
    return []