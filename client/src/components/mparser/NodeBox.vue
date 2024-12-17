<!--suppress ALL -->

<script setup>
import { useDark } from "@vueuse/core";
import { computed } from "vue";
import { icons } from "@/libs/Utils.js";

const props = defineProps({
  // 简化核心数据结构
  modelValue: {
    type: Object,
    required: true,
    default: () => ({})
  },
  // 图标配置，提供默认值
  icon: {
    type: String,
    default: 'AiFillDatabase'
  },
  loading: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:modelValue', 'status-check', 'delete', 'edit']);

const isDark = useDark();

// 简化计算属性
const switchEnabled = computed({
  get: () => props.modelValue.Switch === 1,
  set: (value) => handleSwitchChange(value)
});

const statusClass = computed(() => ({
  'online': switchEnabled.value && props.modelValue.Status === 1,
  'offline': switchEnabled.value && props.modelValue.Status === 0,
  'disabled': !switchEnabled.value,
  'dark-mode': isDark.value
}));

// 简化事件处理
const handleSwitchChange = (newValue) => {
  emit('update:modelValue', {
    ...props.modelValue,
    Switch: newValue ? 1 : 0
  });
};

const handleStatusCheck = () => emit('status-check', props.modelValue);
const handleDelete = () => emit('delete', props.modelValue);
const handleEdit = () => emit('edit', props.modelValue);
</script>

<template>
  <div class="node-box" :class="{'dark-mode': isDark}">
    <div class="box-line">
      <div class="node-status-box" :class="{ 'dark-mode': isDark }">
        <template v-if="!loading">
          <el-tooltip 
            effect="dark" 
            :content="statusClass.online ? '在线' : '离线'" 
            placement="top"
          >
            <component 
              :is="icons[icon]" 
              class="node-status" 
              :class="statusClass"
              @click="handleStatusCheck"
            />
          </el-tooltip>
        </template>
        <div v-else class="loading-container">
          <el-icon class="is-loading">
            <svg class="loading-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
              <path fill="currentColor" d="M512 64a32 32 0 0 1 32 32v192a32 32 0 0 1-64 0V96a32 32 0 0 1 32-32zm0 640a32 32 0 0 1 32 32v192a32 32 0 1 1-64 0V736a32 32 0 0 1 32-32zm448-192a32 32 0 0 1-32 32H736a32 32 0 1 1 0-64h192a32 32 0 0 1 32 32zm-640 0a32 32 0 0 1-32 32H96a32 32 0 0 1 0-64h192a32 32 0 0 1 32 32zM195.2 195.2a32 32 0 0 1 45.248 0L376.32 331.008a32 32 0 0 1-45.248 45.248L195.2 240.448a32 32 0 0 1 0-45.248zm452.544 452.544a32 32 0 0 1 45.248 0L828.8 783.552a32 32 0 0 1-45.248 45.248L647.744 692.992a32 32 0 0 1 0-45.248zM828.8 195.264a32 32 0 0 1 0 45.184L692.992 376.32a32 32 0 0 1-45.248-45.248l135.808-135.808a32 32 0 0 1 45.248 0zm-452.544 452.48a32 32 0 0 1 0 45.248L240.448 828.8a32 32 0 0 1-45.248-45.248l135.808-135.808a32 32 0 0 1 45.248 0z"/>
            </svg>
          </el-icon>
        </div>
      </div>
      <div class="title-container">
        <el-tooltip effect="dark" :content="modelValue.NDSName" placement="top" :show-after="500">
          <span class="node-title">{{ modelValue.NDSName }}</span>
        </el-tooltip>
      </div>
      <el-tooltip effect="dark" :content="switchEnabled ? '已启用' : '已禁用'" placement="top">
        <el-switch 
          v-model="switchEnabled"
          size="small" 
          class="node-switch" 
          :disabled="loading"
        />
      </el-tooltip>
    </div>
    
    <slot></slot>
    
    <div class="box-line actions">
      <el-tooltip effect="dark" content="删除" placement="bottom">
        <el-button 
          size="small" 
          type="danger" 
          :icon="icons['EpDelete']" 
          @click="handleDelete"
          :disabled="loading"
        />
      </el-tooltip>
      <span class="state-text">{{ modelValue.state }}</span>
      <el-tooltip effect="dark" content="详情" placement="bottom">
        <el-button 
          size="small" 
          type="primary" 
          :icon="icons['BsInfoLg']" 
          @click="handleEdit"
          :disabled="loading"
          style="margin-right: 10px;"
        />
      </el-tooltip>
    </div>
  </div>
</template>

<style scoped>
.node-box {
  width: 200px;
  border: 1.5px solid rgb(198, 208, 212);
  margin: 10px;
  padding: 10px;
  background-color: #f7f9ff;
  border-radius: 15px;
  box-shadow: 
    4px 4px 4px rgba(0, 0, 0, 0.219),
    8px 8px 8px rgba(0, 0, 0, 0.26),
    12px 12px 12px rgba(0, 0, 0, 0.06);
  display: flex;
  flex-direction: column;
}

.node-box.dark-mode {
  background-color: #213652;
  border-color: lightgray;
  box-shadow: 
    4px 4px 4px rgba(161, 161, 161, 0.2),
    8px 8px 8px rgba(161, 161, 161, 0.15),
    12px 12px 12px rgba(161, 161, 161, 0.1);
}

.box-line {
  padding: 3px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  width: 100%;
}

.title-container {
  flex: 1;
  min-width: 0;
  margin: 0 10px;
  padding-left: 20px;
  text-align: center;
  display: flex;
  justify-content: center;
}

.node-title {
  font-size: 15px;
  font-weight: bold;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: inline-block;
  max-width: 100%;
}

.node-switch {
  flex-shrink: 0;
  margin-right: 10px;
  --el-switch-on-color: #13ce66;
  --el-switch-off-color: #ff5454;
}

.node-status-box {
  position: absolute;
  left: 10px;
  width: 16px;
  height: 16px;
  display: flex;
  z-index: 1;
  align-items: center;
  justify-content: center;
  background: transparent !important;
}

.node-status {
  width: 16px;
  height: 16px;
  color: #878787;
  cursor: pointer;
  outline: none;
}

.node-status:focus {
  outline: none;
}

.node-status.online {
  color: #13ce66;
}

.node-status.offline {
  color: #ff5454;
}

.node-status.disabled {
  color: #878787;
}

.state-text {
  font-size: 12px;
  color: grey;
}

.actions {
  justify-content: space-between;
  margin: 0 5px;
}

.loading-container {
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-icon {
  width: 16px;
  height: 16px;
  color: var(--el-color-primary);
  animation: rotating 2s linear infinite;
}

@keyframes rotating {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}
</style>
