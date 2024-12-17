<!--suppress JSUnresolvedReference, CssUnusedSymbol -->
<template>
    <div class="nodes-toolbar" :class="{ 'dark-mode': isDark }">
      <div class="search-container">
        <el-input
          v-model="searchInput"
          placeholder="搜索NDS..."
          style="width: 200px"
          clearable
          @clear="handleClear"
          @keyup.enter="handleSearch"
        >
        </el-input>
        <el-button
          type="primary"
          @click="handleSearch"
          :loading="buttonLoading.search"
          :disabled="buttonLoading.search"
        >
          <template v-if="!buttonLoading.search">搜索</template>
        </el-button>
      </div>
      <div class="action-container">
        <el-button
          type="success"
          @click="fetchNDSList"
          :loading="buttonLoading.refresh"
          :disabled="buttonLoading.refresh"
        >
          <template v-if="!buttonLoading.refresh">
            <el-icon><Refresh /></el-icon>
          </template>
        </el-button>
        <el-button
          type="primary"
          @click="openDialog(false)"
          :loading="buttonLoading.submit"
          :disabled="buttonLoading.submit"
        >
          <template v-if="!buttonLoading.submit">添加NDS</template>
        </el-button>
      </div>
    </div>
    <div
      class="nodes-list"
      :class="{ 'dark-mode': isDark }"
      v-loading="loading"
      element-loading-text="加载中..."
      element-loading-background="rgba(0, 0, 0, 0.1)"
    >
      <div class="nodes" ref="nodesContainer">
        <template v-if="!loading">
          <template v-if="ndsList.length > 0">
            <el-scrollbar height="100%" ref="scrollbar">
              <div class="virtual-list-container">
                <node-box
                  v-for="(item, index) in displayedNodes"
                  :key="item.ID"
                  :model-value="{
                    ...item,
                    icon: 'AiFillDatabase',
                    id: item.ID,
                    status: item.Status === 1 ? 'online' : 'offline'
                  }"
                  :loading="item.loading"
                  @update:model-value="updateNodeData(index, $event)"
                  @status-check="checkNDSStatus"
                  @delete="deleteNDS"
                  @edit="openDialog(true, $event)"
                >
                  <div class="box-line" style="margin: 6px 0">
                    <span style="font-size: 13px">
                      IP: {{ formatDate(item.AddTime) }}<br>
                      协议类型: {{ item.Protocol }}
                    </span>
                  </div>
                </node-box>
              </div>
            </el-scrollbar>
          </template>
          <el-empty
            v-else
            description="当前没有NDS配置"
            :image-size="200"
          >
            <el-button type="primary" @click="openDialog(false)">
              添加NDS
            </el-button>
          </el-empty>
        </template>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑NDS' : '添加NDS'" width="520">
      <div style="max-height: 500px; overflow-y: auto; margin-bottom: 16px">
        <el-form :model="currentNDS" ref="ndsForm" :rules="rules">
          <el-form-item label="名称" prop="NDSName" :label-width="formLabelWidth">
            <el-input v-model="currentNDS.NDSName"></el-input>
          </el-form-item>
          <el-form-item label="IP地址" prop="Address" :label-width="formLabelWidth">
            <el-input v-model="currentNDS.Address"></el-input>
          </el-form-item>
          <el-form-item label="端口" prop="Port" :label-width="formLabelWidth">
            <el-input v-model="currentNDS.Port" type="number"></el-input>
          </el-form-item>
          <el-form-item label="协议" prop="Protocol" :label-width="formLabelWidth">
            <el-select v-model="currentNDS.Protocol">
              <el-option label="FTP" value="FTP"></el-option>
              <el-option label="SFTP" value="SFTP"></el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="账号" prop="Account" :label-width="formLabelWidth">
            <el-input class="nds-user" v-model="currentNDS.Account"></el-input>
          </el-form-item>
          <el-form-item label="密码" prop="Password" :label-width="formLabelWidth">
            <el-input v-model="currentNDS.Password" show-password></el-input>
          </el-form-item>
          <el-form-item label="MRO路径" prop="MRO_Path" :label-width="formLabelWidth">
            <el-input v-model="currentNDS.MRO_Path"></el-input>
          </el-form-item>
          <el-form-item label="MRO识别" prop="MRO_Filter" :label-width="formLabelWidth">
            <el-input v-model="currentNDS.MRO_Filter"></el-input>
          </el-form-item>
          <el-form-item label="MDT路径" prop="MDT_Path" :label-width="formLabelWidth">
            <el-input v-model="currentNDS.MDT_Path"></el-input>
          </el-form-item>
          <el-form-item label="MDT识别" prop="MDT_Filter" :label-width="formLabelWidth">
            <el-input v-model="currentNDS.MDT_Filter"></el-input>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="isEdit ? editNDSInfo() : addNDS()">
            {{ isEdit ? '保存' : '添加' }}
          </el-button>
        </span>
      </template>
    </el-dialog>
</template>

<script setup>
import NodeBox from "@/components/mparser/NodeBox.vue";
import { useDark } from "@vueuse/core";
import { ref, computed, reactive, onMounted, onUnmounted, nextTick } from "vue";
import { showMsg } from "@/libs/Utils.js";
import { GetNDSList, AddNDSItem, UpdateNDSItem, DeleteNDSItem } from "@/apis/mparser/NDS";
import { Refresh } from '@element-plus/icons-vue';
import { ElMessageBox } from 'element-plus';
import { debounce } from 'lodash-es';

// 基础状态
const isDark = useDark();
const loading = ref(false);
const dialogVisible = ref(false);
const isEdit = ref(false);
const ndsForm = ref(null);
const ndsList = ref([]);
const searchInput = ref('');
const activeSearch = ref('');
const formLabelWidth = "100px";

// 按钮加载状态
const buttonLoading = ref({
  refresh: false,
  search: false,
  submit: false
});

// NDS默认配置
const defaultNDS = {
  ID: null,
  NDSName: '',
  Address: '',
  Port: 21,
  Protocol: 'FTP',
  Account: '',
  Password: '',
  Status: 1,
  Switch: 1,
  MRO_Path: '/MR/MRO',
  MRO_Filter: 'MRO_ZTE_OMC1_',
  MDT_Path: '/MR/MDT',
  MDT_Filter: 'MDT_ZTE_OMC1_'
};

const currentNDS = reactive({ ...defaultNDS });

// 表单验证规则
const rules = {
  NDSName: [{ required: true, message: '请输入NDS名称', trigger: 'blur' }],
  Address: [{ required: true, message: '请输入IP地址', trigger: 'blur' }],
  Port: [{ required: true, message: '请输入端口号', trigger: 'blur' }],
  Protocol: [{ required: true, message: '请选择协议类型', trigger: 'change' }]
};

// 计算属性：过滤后的NDS列表
const displayedNodes = computed(() => {
  if (!activeSearch.value) return ndsList.value;
  const query = activeSearch.value.toLowerCase();
  return ndsList.value.filter(item =>
    item.NDSName.toLowerCase().includes(query) ||
    item.Address.toLowerCase().includes(query) ||
    item.Protocol.toLowerCase().includes(query)
  );
});

// 通用加载状态处理
const withLoading = async (key, action) => {
  buttonLoading.value[key] = true;
  try {
    return await action();
  } finally {
    buttonLoading.value[key] = false;
  }
};

// 搜索处理
const handleSearch = debounce(() => {
  withLoading('search', () => {
    activeSearch.value = searchInput.value;
  });
}, 300);

const handleClear = () => {
  searchInput.value = '';
  activeSearch.value = '';
};

// 格式化日期
const formatDate = (date) => date ? new Date(date).toLocaleString() : '';

// 添加容器引用
const nodesContainer = ref(null);
const scrollbar = ref(null);

// 优化后的数据加载
const fetchNDSList = async () => {
  loading.value = true;
  try {
    const result = await GetNDSList();
    ndsList.value = result.list || [];

    // 等待DOM更新后重置滚动位置
    await nextTick(() => {
      if (scrollbar.value) {
        scrollbar.value.setScrollTop(0);
      }
    });
  } finally {
    loading.value = false;
  }
};

const updateNodeData = async (_index, newData) => {
  const node = ndsList.value.find(item => item.ID === newData.ID);
  if (!node) return;

  if (newData.Switch !== node.Switch) {
    node.loading = true;
    try {
      const success = await UpdateNDSItem({ ...node, Switch: newData.Switch });
      if (success) {
        node.Switch = newData.Switch;
      } else {
        await showMsg('更新失败', 'error');
      }
    } finally {
      node.loading = false;
    }
  }
};

// 对话框操作
const openDialog = (edit, info = null) => {
  isEdit.value = edit;
  Object.assign(currentNDS, edit && info ?
    ndsList.value.find(item => item.ID === info.id) :
    defaultNDS
  );
  dialogVisible.value = true;
};

const handleSubmit = async () => {
  if (!ndsForm.value) return;

  await ndsForm.value.validate(async (valid) => {
    if (valid) {
      await withLoading('submit', async () => {
        const action = isEdit.value ? UpdateNDSItem : AddNDSItem;
        const success = await action(currentNDS);
        if (success) {
          await fetchNDSList();
          dialogVisible.value = false;
        }
      });
    }
  });
};

const deleteNDS = async (info) => {
  try {
    await ElMessageBox.confirm('确定要删除此NDS吗？', '提示', {
      type: 'warning'
    });

    const node = ndsList.value.find(item => item.ID === info.id);
    if (!node) return;

    node.loading = true;
    const success = await DeleteNDSItem(info.id);

    if (success) {
      ndsList.value = ndsList.value.filter(item => item.ID !== info.id);
      await showMsg('删除成功', 'success');
    }
  } catch (error) {
    if (error !== 'cancel') {
      await showMsg('删除失败', 'error');
    }
  } finally {
    if (node) node.loading = false;
  }
};

// 状态检查
const checkNDSStatus = () => showMsg('正在检查NDS状态...', 'info');

// 生命周期
onMounted(fetchNDSList);

// 优化滚动性能
let scrollTimer = null;

const scrollHandler = () => {
  if (scrollTimer) clearTimeout(scrollTimer);
  scrollTimer = setTimeout(() => {
    // 可以在这里添加滚动优化逻辑
  }, 100);
};

onMounted(() => {
  const scrollbar = document.querySelector('.el-scrollbar__wrap');
  if (scrollbar) {
    scrollbar.addEventListener('scroll', scrollHandler);
  }
});

onUnmounted(() => {
  if (scrollTimer) clearTimeout(scrollTimer);
  const scrollbar = document.querySelector('.el-scrollbar__wrap');
  if (scrollbar) {
    scrollbar.removeEventListener('scroll', scrollHandler);
  }
});

// 添加编辑和添加的具体处理方法
const addNDS = () => handleSubmit();
const editNDSInfo = () => handleSubmit();
</script>

<style scoped>
.nodes-toolbar {
    top: 0;
    display: flex;
    justify-content: space-between;
    padding: 10px 20px;
    background-color: white;
    z-index: 10;
    box-shadow: 0 3px 6px rgba(0, 0, 0, .12), 0 0 6px rgba(0, 0, 0, .04);
}

.nodes-toolbar.dark-mode {
    background-color: #1f1f1f;
    box-shadow: 0 3px 6px rgba(255, 255, 255, 0.12), 0 0 6px rgba(255, 255, 255, 0.04);
}

.nodes-list {
    height: calc(100% - 52px);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 20px;
    box-sizing: border-box;
    box-shadow: 0 8px 16px rgba(0, 0, 0, .12), 0 0 6px rgba(0, 0, 0, .04);
    position: relative;
}

.nodes-list.dark-mode {
    background-color: #1f1f1f;
    box-shadow: 0 3px 6px rgba(255, 255, 255, 0.12), 0 0 6px rgba(255, 255, 255, 0.04);
}

.nodes {
    display: block;
    width: 100%;
    height: 100%;
    overflow: hidden;
    position: relative;
}

.box-line {
    padding: 3px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    position: relative;
}

.search-container {
    display: flex;
    gap: 10px;
    align-items: center;
}

.action-container {
    display: flex;
    gap: 10px;
    align-items: center;
}

:deep(.el-empty) {
    padding: 40px 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    width: 100%;
}

/* 添加禁用状态下的按钮样式 */
:deep(.el-button.is-disabled) {
  cursor: not-allowed;
}

/* 添加加载状态的样式调整 */
.nodes-list {
    height: calc(100% - 52px);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 20px;
    box-sizing: border-box;
    box-shadow: 0 8px 16px rgba(0, 0, 0, .12), 0 0 6px rgba(0, 0, 0, .04);
    position: relative;
}

/* 自定义加载图标的样式 */
:deep(.el-loading-mask) {
    background-color: rgba(255, 255, 255, 0.7);
}

:deep(.el-loading-spinner .el-loading-text) {
    color: var(--el-color-primary);
}

/* 暗黑模式下的加载样式 */
.dark-mode :deep(.el-loading-mask) {
    background-color: rgba(0, 0, 0, 0.7);
}

.dark-mode :deep(.el-loading-spinner .el-loading-text) {
    color: var(--el-color-primary);
}

.virtual-list-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, 220px);
  gap: 60px;
  padding: 20px;
  justify-content: center;
  width: 100%;
  box-sizing: border-box;
}

/* NodeBox 固定宽度布局 */
.virtual-list-container :deep(.node-box) {
  width: 220px !important;
  margin: 0;
}

/* 移除不需要的样式 */
.virtual-list-container:only-child {
  grid-template-columns: repeat(auto-fit, 220px);
}
</style>
