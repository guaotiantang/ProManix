
<!--suppress CssUnusedSymbol, JSValidateTypes, JSUnresolvedReference -->
<template>
  <div class="cell-data-container">
    <!-- 搜索栏和工具栏 -->
    <div class="header-container" ref="headerContainer">
      <!-- 搜索栏 -->
      <div class="search-section">
        <el-form :inline="true" :model="searchForm" class="search-form" @submit.prevent="handleSearch">
          <el-form-item class="search-item">
            <template #label>
              <span class="search-label">搜索</span>
            </template>
            <el-select
              v-model="searchForm.field"
              placeholder="请选择搜索字段"
              class="field-select"
            >
              <el-option label="全部字段" value="all" />
              <el-option label="CGI" value="CGI" />
              <el-option label="eNodeBID" value="eNodeBID" />
              <el-option label="PCI" value="PCI" />
              <el-option label="Azimuth" value="Azimuth" />
              <el-option label="Earfcn" value="Earfcn" />
              <el-option label="Freq" value="Freq" />
              <el-option label="eNBName" value="eNBName" />
              <el-option label="userLabel" value="userLabel" />
            </el-select>
            <el-input
              v-model="searchForm.keyword"
              placeholder="请输入搜索内容"
              class="keyword-input"
              clearable
              @keyup.enter="handleSearch"
            />
            <el-button
              type="primary"
              @click="handleSearch"
              :loading="buttonLoading.search"
              :disabled="buttonLoading.search"
            >
              <template v-if="!buttonLoading.search">搜索</template>
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- 工具栏 -->
      <div class="toolbar">
        <el-button
          @click="fetchData"
          :loading="buttonLoading.refresh"
          :disabled="buttonLoading.refresh"
        >
          <template v-if="!buttonLoading.refresh">
            <el-icon><component :is="icons['EpRefresh']" /></el-icon>
          </template>
        </el-button>

        <el-button
          type="primary"
          @click="handleAdd"
          :loading="buttonLoading.submit"
          :disabled="buttonLoading.submit"
        >
          <template v-if="!buttonLoading.submit">新增</template>
        </el-button>

        <el-upload
          class="upload-demo"
          :action="null"
          :http-request="handleUpload"
          :show-file-list="false"
          :before-upload="beforeUpload"
          :disabled="buttonLoading.upload"
          accept=".xlsx,.xls"
        >
          <el-button
            type="success"
            :loading="buttonLoading.upload"
            :disabled="buttonLoading.upload"
          >
            <template v-if="!buttonLoading.upload">上传</template>
          </el-button>
        </el-upload>

        <el-button
          type="primary"
          @click="handleExport"
          :loading="buttonLoading.export"
          :disabled="buttonLoading.export"
        >
          <template v-if="!buttonLoading.export">导出</template>
        </el-button>
      </div>
    </div>

    <!-- 数据表格 -->
    <el-table
      :data="tableData"
      style="width: 100%"
      height="100%"
      border
      @sort-change="handleSortChange"
      @selection-change="handleSelectionChange"
    >
      <template v-for="col in columns" :key="col.prop || col.type">
        <el-table-column v-if="col.slot" v-bind="col">
          <template #default="scope">
            <el-button
              size="small"
              @click="handleEdit(scope.row)"
            >修改</el-button>
            <el-button
              size="small"
              type="danger"
              @click="handleDelete(scope.row)"
            >删除</el-button>
          </template>
        </el-table-column>
        <el-table-column v-else v-bind="col" />
      </template>
    </el-table>

    <!-- 底部操作区域 -->
    <div class="bottom-container">
      <!-- 批量删除按钮 -->
      <div class="batch-delete-container">
        <el-button
          type="danger"
          @click="handleBatchDelete"
          :disabled="!selectedRows.length"
        >批量删除</el-button>
        <span class="selected-count" v-if="selectedRows.length">
          已选择 {{ selectedRows.length }} 项
        </span>
      </div>

      <!-- 分页容器 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[50, 100, 200, 500]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          @size-change="handleSizeChange"
          @current-change="handleCurrentChange"
        />
      </div>
    </div>

    <!-- 编辑/新增对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="500px"
      @close="resetForm"
    >
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="100px"
        label-position="right"
        @submit.prevent
      >
        <el-form-item label="CGI" prop="CGI">
          <el-input
            v-model="form.CGI"
            placeholder="请输入CGI"
            :disabled="dialogTitle === '编辑小区信息'"
            @input="handleCGIInput"
          />
        </el-form-item>
        <el-form-item label="eNodeBID" prop="eNodeBID">
          <el-input
            v-model="form.eNodeBID"
            placeholder="请输入eNodeBID"
            @input="validateNumber($event, 'eNodeBID')"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="PCI" prop="PCI">
          <el-input
            v-model="form.PCI"
            placeholder="请输入PCI (0-1024)"
            @input="validateNumber($event, 'PCI')"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="Azimuth" prop="Azimuth">
          <el-input
            v-model="form.Azimuth"
            placeholder="请输入Azimuth (0-360)"
            @input="validateNumber($event, 'Azimuth')"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="Earfcn" prop="Earfcn">
          <el-input
            v-model="form.Earfcn"
            placeholder="请输入Earfcn"
            @input="validateNumber($event, 'Earfcn')"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="Freq" prop="Freq">
          <el-input
            v-model="form.Freq"
            placeholder="请输入Freq"
            @input="validateNumber($event, 'Freq')"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="eNBName" prop="eNBName">
          <el-input v-model="form.eNBName" placeholder="请输入eNBName" />
        </el-form-item>
        <el-form-item label="userLabel" prop="userLabel">
          <el-input v-model="form.userLabel" placeholder="请输入userLabel" />
        </el-form-item>
        <el-form-item label="经度" prop="Longitude">
          <el-input
            v-model="form.Longitude"
            placeholder="请输入经度 (-180到180)"
            @input="validateNumber($event, 'Longitude')"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="纬度" prop="Latitude">
          <el-input
            v-model="form.Latitude"
            placeholder="请输入纬度 (-90到90)"
            @input="validateNumber($event, 'Latitude')"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button
            type="primary"
            @click="handleSubmit(formRef)"
            :loading="buttonLoading.submit"
            :disabled="buttonLoading.submit"
          >
            <template v-if="!buttonLoading.submit">确定</template>
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import {computed, nextTick, onMounted, onUnmounted, ref} from 'vue'
import {icons} from '@/libs/Utils.js'
import {
  AddCellData,
  BatchDeleteCellData,
  DeleteCellData,
  ExportExcel,
  GetCellDataList,
  UpdateCellData,
  UploadExcel
} from '@/apis/mparser/CellData'
import {showMsg} from '@/libs/Utils'
import {debounce} from 'lodash-es'
import {ElLoading} from 'element-plus'

// 响应式数据

const tableData = ref([])
const currentPage = ref(1)
const pageSize = ref(50)
const total = ref(0)
const selectedRows = ref([])
const dialogVisible = ref(false)
const dialogTitle = ref('新增小区信息')
const formRef = ref(null)
const headerContainer = ref(null)
const headerWidth = ref(0)
const buttonLoading = ref({
  refresh: false,
  search: false,
  submit: false,
  upload: false,
  export: false
})


// 搜索表单
const searchForm = ref({
  field: 'all',
  keyword: ''
})

// 编辑表单
const form = ref({
  CGI: '',
  eNodeBID: null,
  PCI: null,
  Azimuth: null,
  Earfcn: null,
  Freq: null,
  eNBName: '',
  userLabel: '',
  Longitude: null,
  Latitude: null
})

// 数字输入验证函数
const validateNumber = (value, field) => {
  form.value[field] = value;
  if (value === '') {
    form.value[field] = null;
    return;
  }
  formRef.value?.validateField(field);
};

// 自定义验证规则
const rules = {
  CGI: [
    { required: true, message: '请输入CGI', trigger: 'change' },
    {
      pattern: /^\d{3}-\d{2}-\d{6,8}-\d+$/,
      message: 'CGI格式不正确 (例: 460-00-123456-1)',
      trigger: 'change'
    }
  ],
  eNodeBID: [
    { required: true, message: '请输入eNodeBID', trigger: 'change' },
    {
      validator: (rule, value, callback) => {
        if (value === null || value === '') {
          callback(new Error('请输入eNodeBID'));
          return;
        }
        const num = Number(value);
        if (isNaN(num) || num < 0 || num > 99999999 || !Number.isInteger(num)) {
          callback(new Error('eNodeBID必须是0-99999999之间的整数'));
          return;
        }
        callback();
      },
      trigger: 'change'
    }
  ],
  PCI: [
    { required: true, message: '请输入PCI', trigger: 'change' },
    {
      validator: (rule, value, callback) => {
        if (value === null || value === '') {
          callback(new Error('请输入PCI'));
          return;
        }
        const num = Number(value);
        if (isNaN(num) || num < 0 || num > 1024 || !Number.isInteger(num)) {
          callback(new Error('PCI必须是0-1024之间的整数'));
          return;
        }
        callback();
      },
      trigger: 'change'
    }
  ],
  Azimuth: [
    { required: true, message: '请输入方位角', trigger: 'change' },
    {
      validator: (rule, value, callback) => {
        if (value === null || value === '') {
          callback(new Error('请输入方位角'));
          return;
        }
        const num = Number(value);
        if (isNaN(num) || num < 0 || num > 360) {
          callback(new Error('方位角必须在0-360之间'));
          return;
        }
        callback();
      },
      trigger: 'change'
    }
  ],
  Earfcn: [
    { required: true, message: '请输入Earfcn', trigger: 'change' },
    {
      validator: (rule, value, callback) => {
        if (value === null || value === '') {
          callback(new Error('请输入Earfcn'));
          return;
        }
        const num = Number(value);
        if (isNaN(num) || num < 0 || !Number.isInteger(num)) {
          callback(new Error('Earfcn必须是大于0的整数'));
          return;
        }
        callback();
      },
      trigger: 'change'
    }
  ],
  Freq: [
    { required: true, message: '请输入Freq', trigger: 'change' },
    {
      validator: (rule, value, callback) => {
        if (value === null || value === '') {
          callback(new Error('请输入Freq'));
          return;
        }
        const num = Number(value);
        if (isNaN(num) || num < 0 || !Number.isInteger(num)) {
          callback(new Error('Freq必须是大于0的整数'));
          return;
        }
        callback();
      },
      trigger: 'change'
    }
  ],
  Longitude: [
    { required: true, message: '请输入经度', trigger: 'change' },
    {
      validator: (rule, value, callback) => {
        if (value === null || value === '') {
          callback(new Error('请输入经度'));
          return;
        }
        const num = Number(value);
        if (isNaN(num) || num < -180 || num > 180) {
          callback(new Error('经度必须在-180到180之间'));
          return;
        }
        callback();
      },
      trigger: 'change'
    }
  ],
  Latitude: [
    { required: true, message: '请输入纬度', trigger: 'change' },
    {
      validator: (rule, value, callback) => {
        if (value === null || value === '') {
          callback(new Error('请输入纬度'));
          return;
        }
        const num = Number(value);
        if (isNaN(num) || num < -90 || num > 90) {
          callback(new Error('纬度必须在-90到90之间'));
          return;
        }
        callback();
      },
      trigger: 'change'
    }
  ]
};

// 重置表单
const resetForm = () => {
  if (formRef.value) {
    formRef.value.resetFields();
  }
  form.value = {
    CGI: '',
    eNodeBID: null,
    PCI: null,
    Azimuth: null,
    Earfcn: null,
    Freq: null,
    eNBName: '',
    userLabel: '',
    Longitude: null,
    Latitude: null
  };
};

// 提交表单
const handleSubmit = async (formEl) => {
  if (!formEl) return;

  try {
    await formEl.validate();

    // 数据类型转换和验证
    const formData = {
      ...form.value,
      eNodeBID: parseInt(form.value.eNodeBID),
      PCI: parseInt(form.value.PCI),
      Azimuth: parseFloat(form.value.Azimuth),
      Earfcn: parseInt(form.value.Earfcn),
      Freq: parseInt(form.value.Freq),
      Longitude: parseFloat(form.value.Longitude),
      Latitude: parseFloat(form.value.Latitude)
    };

    // 额外的数据验证
    if (isNaN(formData.eNodeBID) || isNaN(formData.PCI) || isNaN(formData.Azimuth) ||
        isNaN(formData.Earfcn) || isNaN(formData.Freq) ||
        isNaN(formData.Longitude) || isNaN(formData.Latitude)) {
      throw new Error('请输入有效的数字');
    }

    buttonLoading.value.submit = true;

    if (dialogTitle.value === '新增小区信息') {
      await AddCellData(formData);
      await showMsg('添加成功');
    } else {
      await UpdateCellData(formData);
      await showMsg('更新成功');
    }

    dialogVisible.value = false;
    await fetchData();
  } finally {
    buttonLoading.value.submit = false;
  }
};

// 获数据
const fetchData = async () => {
  buttonLoading.value.refresh = true
  try {
    const data = await GetCellDataList(
      currentPage.value,
      pageSize.value,
      searchForm.value.field,
      searchForm.value.keyword
    )
    if (data) {
      tableData.value = data.list || []
      total.value = data.total || 0
    }
  } finally {
    buttonLoading.value.refresh = false
  }
}

// 防抖处理搜索
const handleSearch = debounce(async () => {
  buttonLoading.value.search = true
  try {
    currentPage.value = 1
    await fetchData()
  } finally {
    buttonLoading.value.search = false
  }
}, 300)

// 处理分页大小变化
const handleSizeChange = (val) => {
  pageSize.value = val
  fetchData()
}

// 处理页码变化
const handleCurrentChange = (val) => {
  currentPage.value = val
  fetchData()
}

// 处理选择变化
const handleSelectionChange = (val) => {
  selectedRows.value = val
}

// 处理新增
const handleAdd = () => {
  dialogTitle.value = '新增小区信息'
  resetForm()
  dialogVisible.value = true
}

// 处理编辑
const handleEdit = (row) => {
  dialogTitle.value = '编辑小区信息'
  Object.keys(form.value).forEach(key => {
    if (['eNodeBID', 'PCI', 'Azimuth', 'Earfcn', 'Freq', 'Longitude', 'Latitude'].includes(key)) {
      form.value[key] = Number(row[key])
    } else {
      form.value[key] = row[key]
    }
  })
  dialogVisible.value = true
}

// 处理删除
const handleDelete = async (row) => {
  const confirmed = await showMsg(`确认删除 ${row.CGI} 吗？`, 'inquire')
  if (confirmed) {
    const success = await DeleteCellData(row.CGI)
    if (success) {
      await fetchData()
    }
  }
}

// 处理批量删除
const handleBatchDelete = async () => {
  if (selectedRows.value.length === 0) {
    await showMsg('请选择要删除的数据', 'warning')
    return
  }

  const confirmed = await showMsg(`确认删除选中的 ${selectedRows.value.length} 项数据吗？`, 'inquire')
  if (confirmed) {
    const cgis = selectedRows.value.map(row => row['CGI'])
    const success = await BatchDeleteCellData(cgis)
    if (success) {
      await fetchData()
    }
  }
}

// 处理导出
const handleExport = async () => {
  buttonLoading.value.export = true
  const loadingInstance = ElLoading.service({
    text: '正在导出数据，请稍候...',
    background: 'rgba(0, 0, 0, 0.7)'
  })

  try {
    await ExportExcel()
    await showMsg('导出成功', 'success')
  } finally {
    loadingInstance.close()
    buttonLoading.value.export = false
  }
}

// 文件上传前的验证
const beforeUpload = async (file) => {
  const isExcel = file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' ||
                  file.type === 'application/vnd.ms-excel'
  const isLt50M = file.size / 1024 / 1024 < 50

  if (!isExcel) {
    await showMsg('只能上传 Excel 文件!', 'error')
    return false
  }
  if (!isLt50M) {
    await showMsg('文件大小不能超 50MB!', 'error')
    return false
  }

  // 添加确认对话框
  return await showMsg(
      `确认上传文件 ${file.name} 吗？<br>上传后将自动更新数据。`,
      'inquire'
  )
}

// 处理文件上传
const handleUpload = async (options) => {
  buttonLoading.value.upload = true
  const loadingInstance = ElLoading.service({
    text: '正在更新数据, 请稍候...',
    background: 'rgba(0, 0, 0, 0.7)'
  })

  try {
    const result = await UploadExcel(options.file)
    if (result) {
      const { total, inserted, updated, failed, successRate } = result.results
      await showMsg(
        `文件处理完成<br>
         总: ${total}条<br>
         新增: ${inserted}条<br>
         更新: ${updated}条<br>
         失败: ${failed}条<br>
         成功率: ${successRate}`,
        'success',
        10000,
        true,
        true,
        100,
        true
      )
      await fetchData()
    }
  } finally {
    loadingInstance.close()
    buttonLoading.value.upload = false
  }
}

// 简化 handleCGIInput 函数
const handleCGIInput = (value) => {
  // 只在新增模式下自动提取 eNodeBID
  if (dialogTitle.value === '新增小区信息' && value) {
    const match = value.match(/^\d{3}-\d{2}-(\d{6,8})-\d+$/);
    if (match && match[1]) {
      const eNodeBID = parseInt(match[1]);
      if (!isNaN(eNodeBID)) {
        form.value.eNodeBID = eNodeBID;
        // 触发验证
        nextTick(() => {
          formRef.value?.validateField('eNodeBID');
        });
      }
    }
  }
};

// 更新头部宽度
const updateHeaderWidth = () => {
  headerWidth.value = headerContainer.value?.offsetWidth || 0
}

// 计算格数据
computed(() => {
  return tableData.value.map(item => ({
    ...item,
    eNBName: item['eNBName'] || '',
    userLabel: item['userLabel'] || '',
  }));
});
// 添加序处理函数
const handleSortChange = ({ prop, order }) => {
  if (!prop || !order) return;

  tableData.value.sort((a, b) => {
    const valueA = a[prop];
    const valueB = b[prop];

    // 数字类型的排序
    if (!isNaN(valueA) && !isNaN(valueB)) {
      return order === 'ascending'
        ? valueA - valueB
        : valueB - valueA;
    }

    // 字符串类型的排序
    return order === 'ascending'
      ? String(valueA).localeCompare(String(valueB))
      : String(valueB).localeCompare(String(valueA));
  });
};

// 列配置
const columns = [
  {type: 'selection', width: '55', fixed: 'left'},
  {prop: 'CGI', label: 'CGI', minWidth: '180', fixed: 'left', resizable: true, showOverflowTooltip: true},
  {prop: 'eNodeBID', label: 'eNodeBID', minWidth: '128', sortable: 'custom', resizable: true, showOverflowTooltip: true},
  {prop: 'PCI', label: 'PCI', minWidth: '80', sortable: 'custom', resizable: true, showOverflowTooltip: true},
  {prop: 'Azimuth', label: 'Azimuth', minWidth: '116', sortable: 'custom', resizable: true, showOverflowTooltip: true},
  {prop: 'Earfcn', label: 'Earfcn', minWidth: '100', sortable: 'custom', resizable: true, showOverflowTooltip: true},
  {prop: 'Freq', label: 'Freq', minWidth: '100', sortable: 'custom', resizable: true, showOverflowTooltip: true},
  {prop: 'eNBName', label: 'eNBName', minWidth: '150', resizable: true, showOverflowTooltip: true},
  {prop: 'userLabel', label: 'userLabel', minWidth: '150', resizable: true, showOverflowTooltip: true},
  {prop: 'Longitude', label: 'Longitude', minWidth: '100', resizable: true, showOverflowTooltip: true},
  {prop: 'Latitude', label: 'Latitude', minWidth: '100', resizable: true, showOverflowTooltip: true},
  {label: '操作', width: '150', fixed: 'right', align: 'center', slot: 'operations'}
];

onMounted(() => {
  fetchData()
  nextTick(() => {
    updateHeaderWidth()
  })
  window.addEventListener('resize', updateHeaderWidth)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateHeaderWidth)
})
</script>

<style scoped>
.cell-data-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.header-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.search-section {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.search-form {
  margin: 0;
}

.search-item {
  margin: 0;
  display: flex;
  align-items: center;
}

.search-item :deep(.el-form-item__label) {
  padding-right: 8px;
}

.search-label {
  white-space: nowrap;
}

.field-select {
  width: 120px;
  margin-right: 8px;
}

.keyword-input {
  width: 200px;
  margin-right: 8px;
}

.toolbar {
  flex-shrink: 0;
  margin-top: 10px;
  display: flex;
  gap: 10px;
}

.upload-demo {
  display: inline-block;
  margin: 0 8px;
}

/* 表格器 */
.el-table {
  flex: 1;
  overflow: auto;
}

.pagination-container {
  margin-top: 0;
  flex-shrink: 0;
}

/* 隐藏el-input-number的控制按钮 */
:deep(.el-input-number .el-input-number__decrease),
:deep(.el-input-number .el-input-number__increase) {
  display: none;
}

/* 让输入框宽度与普通输入框一致 */
:deep(.el-input-number .el-input__wrapper) {
  padding-left: 11px;
  padding-right: 11px;
}

/* 确保内容可水平滚动 */
:deep(.el-table__body-wrapper) {
  overflow-x: auto !important;
}

/* 固定表格高度, 显示垂直滚动条 */
:deep(.el-table__body-wrapper) {
  height: calc(100vh - 250px) !important;
  overflow-y: auto !important;
}

.bottom-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  flex-shrink: 0;
  min-width: max-content;
}

.batch-delete-container {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.selected-count {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.pagination-container {
  margin-top: 0;
  flex-shrink: 0;
}

/* 表头样式 */
:deep(.table-header) {
  background-color: var(--el-color-primary-light-9) !important;
}

/* 优化表格行的悬停效果 */
:deep(.el-table__row:hover) {
  background-color: var(--el-color-primary-light-9) !important;
}

/* 优化固定列样式 */
:deep(.el-table .el-table__fixed) {
  height: 100% !important;
  box-shadow: 6px 0 6px -4px rgba(0,0,0,.12);
}

/* 禁用态下按钮样式 */
:deep(.el-button.is-disabled) {
  cursor: not-allowed;
}

/* 上传按钮禁用状态 */
:deep(.el-upload--text.is-disabled) {
  cursor: not-allowed;
}

/* 优化表格样式 */
:deep(.el-table) {
  --el-table-border-color: var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
}

:deep(.el-table__header-wrapper) {
  background-color: var(--el-fill-color-light);
}

:deep(.el-table__header) {
  th {
    background-color: var(--el-fill-color-light);
    font-weight: 600;
  }
}

:deep(.el-table__body-wrapper) {
  overflow-x: auto !important;
  overflow-y: auto !important;
}

/* 确保固定列的阴影效果 */
:deep(.el-table__fixed-right),
:deep(.el-table__fixed) {
  height: 100% !important;
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
}

/* 优化表格行的悬停效果 */
:deep(.el-table__row:hover) {
  background-color: var(--el-fill-color-lighter) !important;
}

/* 确保单行显示和行高固定 */
:deep(.el-table__row) {
  height: 40px !important;
}

:deep(.el-table__cell) {
  padding: 0 !important;
  line-height: 40px !important;
}

/* 可选：美化表格样式 */
:deep(.el-table--border) {
  border-radius: 4px;
  overflow: hidden;
}

:deep(.el-table__header-wrapper) {
  background-color: #f5f7fa;
}

:deep(.el-table__header th) {
  background-color: #f5f7fa;
  color: #606266;
  font-weight: bold;
  padding: 8px 0;
}

:deep(.el-table__header th.is-right) {
  text-align: center !important;
}

:deep(.el-table__header th.el-table__cell) {
  text-align: center !important;
}

/* 暗黑主题适配 */
:deep(.el-table) {
  --el-table-bg-color: var(--el-bg-color); /* 表格背景色跟随主题 */
  --el-table-tr-bg-color: var(--el-bg-color); /* 行背景色跟随主题 */
  --el-table-header-bg-color: var(--el-bg-color-overlay); /* 表头背景色 */
}

/* 头样式 - 支持暗黑模式 */
:deep(.el-table__header th) {
  background-color: var(--el-bg-color-overlay) !important;
  color: var(--el-text-color-primary);
  font-weight: bold;
  padding: 8px 0;
}

/* 悬停效果 - 支持暗黑模式 */
:deep(.el-table__row:hover td) {
  background-color: var(--el-bg-color-overlay) !important;
}

/* 固定列背景色 - 支持暗黑模式 */
:deep(.el-table__fixed-right-patch) {
  background-color: var(--el-bg-color-overlay);
}

:deep(.el-table__fixed-right),
:deep(.el-table__fixed) {
  background-color: var(--el-bg-color);
}

/* 表格边框颜色 - 支持暗黑模式 */
:deep(.el-table--border),
:deep(.el-table--group) {
  border-color: var(--el-border-color-lighter);
}

:deep(.el-table--border .el-table__cell) {
  border-right: 1px solid var(--el-border-color-lighter);
}

:deep(.el-table__cell) {
  border-bottom: 1px solid var(--el-border-color-lighter);
}

/* 空状态背景色 - 支持暗黑模式 */
:deep(.el-table__empty-block) {
  background-color: var(--el-bg-color);
}

/* 移除之前可能冲突的样式 */
:deep(.el-table__header-wrapper) {
  background-color: unset;
}

/* 移除之前的表格相关样式，使用以下新的样式 */

/* 表格基础样式 */
:deep(.el-table) {
  background-color: transparent;
  --el-table-border-color: var(--el-border-color-lighter);
  border-radius: 4px;
  overflow: hidden;
}

/* 表头样式 */
:deep(.el-table__header th.el-table__cell) {
  background-color: var(--el-fill-color-light) !important;
  color: var(--el-text-color-regular);
  text-align: center !important;
  font-weight: bold;
  padding: 8px 0;
}

/* 固定列样式 */
:deep(.el-table__fixed-right),
:deep(.el-table__fixed-left) {
  background-color: inherit;
}

:deep(.el-table__fixed .el-table__cell),
:deep(.el-table__fixed-right .el-table__cell) {
  background-color: inherit;
}

/* 固定列表头 */
:deep(.el-table__fixed-header-wrapper .el-table__cell),
:deep(.el-table__fixed-right .el-table__header-wrapper .el-table__cell) {
  background-color: var(--el-fill-color-light) !important;
}

/* 悬停效果 */
:deep(.el-table__row:hover td.el-table__cell) {
  background-color: var(--el-fill-color-light) !important;
}

/* 固定列阴影 */
:deep(.el-table__fixed-right) {
  box-shadow: -6px 0 6px -4px rgba(0, 0, 0, 0.12);
}

:deep(.el-table__fixed) {
  box-shadow: 6px 0 6px -4px rgba(0, 0, 0, 0.12);
}

/* 边框样式 */
:deep(.el-table--border),
:deep(.el-table--group) {
  border-color: var(--el-border-color-lighter);
}

:deep(.el-table--border .el-table__cell) {
  border-right: 1px solid var(--el-border-color-lighter);
}

:deep(.el-table__cell) {
  border-bottom: 1px solid var(--el-border-color-lighter);
}

/* 确保单行显示和行高固定 */
:deep(.el-table__row) {
  height: 40px !important;
}

:deep(.el-table__cell) {
  padding: 0 !important;
  line-height: 40px !important;
}

/* 确保表头文字中 */
:deep(.el-table__header th.is-right) {
  text-align: center !important;
}

/* 暗黑模式下的表格背景色 */
:deep(.el-table) {
  --el-table-bg-color: var(--el-bg-color); /* 明亮模式使用默认背景色 */
  --el-table-tr-bg-color: var(--el-bg-color); /* 明亮模式使用默认背景色 */
  --el-table-header-bg-color: var(--el-fill-color-light); /* 表头背景色 */
}

/* 暗黑模式下的具体背景色设置 */
html.dark {
  :deep(.el-table) {
    --el-table-bg-color: #252525;
    --el-table-tr-bg-color: #252525;
  }

  :deep(.el-table__body td.el-table__cell) {
    background-color: #252525 !important;
  }

  :deep(.el-table__fixed-right .el-table__cell),
  :deep(.el-table__fixed .el-table__cell) {
    background-color: #252525 !important;
  }
}
</style>
