<!--suppress JSSuspiciousNameCombination, CssUnusedSymbol, JSUnresolvedReference, JSUnusedGlobalSymbols -->
<template>
  <div class="custom-tabs border" :class="{ 'dark-mode': isDark }">
    <!-- 标签栏 -->
    <div class="tabs-header-wrapper">
      <!-- 左滚动按钮 -->
      <div
        v-show="showLeftButton"
        class="scroll-button left"
        :class="{ 'pressing': isPressingLeft }"
        @mousedown="() => startPress('left')"
        @mouseup="stopPress"
        @mouseleave="stopPress"
        @click="scrollLeft"
      >
        <el-icon><ArrowLeft /></el-icon>
      </div>

      <!-- 标签容器 -->
      <div
        class="tabs-header"
        ref="tabsHeader"
        @wheel.prevent="handleWheel"
      >
        <div
          class="tabs-nav-wrap"
          ref="tabsNav"
          :style="{ transform: `translateX(${-scrollOffset}px)` }"
        >
          <div
            v-for="(tab, index) in tabs"
            :key="tab.path"
            class="tab-item"
            :class="{
              active: tab.path === activeTab,
              'dragging': draggingIndex === index,
              'drag-over': dragOverIndex === index,
              'fixed-tab': pathFilter.includes(tab.path)
            }"
            :draggable="!pathFilter.includes(tab.path)"
            @dragstart="handleDragStart($event, index)"
            @dragend="handleDragEnd"
            @dragover="handleDragOver($event, index)"
            @drop="handleDrop($event, index)"
            @click="switchTab(tab.path)"
            @contextmenu="handleContextMenu($event, tab)"
          >
            <el-icon v-if="tab.icon"><component :is="icons[tab.icon]" /></el-icon>
            <span class="tab-label">{{ truncateText(tab.name, 128) }}</span>
            <el-icon
              v-if="!pathFilter.includes(tab.path)"
              class="close-icon"
              @click.stop="closeTab(tab.path)"
            >
              <Close />
            </el-icon>
          </div>
        </div>
      </div>

      <!-- 右滚动按钮 -->
      <div
        v-show="showRightButton"
        class="scroll-button right"
        :class="{ 'pressing': isPressingRight }"
        @mousedown="() => startPress('right')"
        @mouseup="stopPress"
        @mouseleave="stopPress"
        @click="scrollRight"
      >
        <el-icon><ArrowRight /></el-icon>
      </div>
    </div>

    <!-- 内容区 -->
    <div class="tabs-content">
      <div class="tabs-content-inner">
        <slot></slot>
      </div>
    </div>

    <!-- 右键菜单 -->
    <div
      v-show="showContextMenu"
      class="context-menu"
      :style="{
        left: contextMenuPosition.x + 'px',
        top: contextMenuPosition.y + 'px'
      }"
    >
      <div class="context-menu-item" @click="refreshCurrentTab">刷新当前</div>
      <div
        v-if="contextMenuTab && !pathFilter.includes(contextMenuTab.path)"
        class="context-menu-item"
        @click="closeContextTab"
      >关闭标签</div>
      <div class="context-menu-item" @click="closeOtherTabs">关闭其他</div>
      <div class="context-menu-item" @click="closeAllTabs">关闭全部</div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, nextTick, watch, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { tabStore, themeStore } from '@/store'
import { icons } from '@/libs/Utils.js'
import { Close, ArrowLeft, ArrowRight } from '@element-plus/icons-vue'

const router = useRouter()
const store = tabStore()
const theme = themeStore()

const isDark = computed(() => theme.isDark)
const tabs = computed(() => store.openTab)
const activeTab = computed(() => store.activeIndex)
const pathFilter = store.pathFilter

const tabsHeader = ref(null)
const tabsNav = ref(null)
const scrollOffset = ref(0)
const showLeftButton = ref(false)
const showRightButton = ref(false)

const draggingIndex = ref(null)
const dragOverIndex = ref(null)

const scrollInterval = ref(null)
const pressTimeout = ref(null)
const scrollSpeed = 8 // 每次滚动的像素数
const scrollDelay = 16 // 滚动间隔时间(ms)
const pressDelay = 600 // 长按触发延迟(ms)

const isPressingLeft = ref(false)
const isPressingRight = ref(false)
const contextMenuTab = ref(null)
const showContextMenu = ref(false)
const contextMenuPosition = ref({ x: 0, y: 0 })
const route = useRoute()

// 定义props
const props = defineProps({
  addable: {
    type: Boolean,
    default: false
  },
  beforeClose: {
    type: Function,
    default: null
  },
  beforeAdd: {
    type: Function,
    default: null
  }
})

// 定义emit
const emit = defineEmits(['tab-add', 'tab-remove', 'tab-change'])

// 截断文本
const truncateText = (text, maxLength) => {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

// 检查是否需要显示滚动按钮
const checkScroll = () => {
  if (!tabsHeader.value || !tabsNav.value) return

  const { scrollWidth, clientWidth } = tabsHeader.value
  const { scrollLeft } = tabsHeader.value

  showLeftButton.value = scrollLeft > 0
  showRightButton.value = scrollWidth > clientWidth && scrollLeft < scrollWidth - clientWidth

  scrollOffset.value = scrollLeft
}

// 开始长按
const startPress = (direction) => {
  if (direction === 'left') {
    isPressingLeft.value = true
  } else {
    isPressingRight.value = true
  }

  stopPress()
  pressTimeout.value = setTimeout(() => {
    startScroll(direction)
  }, pressDelay)
}

// 停止长按
const stopPress = () => {
  isPressingLeft.value = false
  isPressingRight.value = false

  if (pressTimeout.value) {
    clearTimeout(pressTimeout.value)
    pressTimeout.value = null
  }
  stopScroll()
}

// 开始滚动
const startScroll = (direction) => {
  stopScroll()

  const scrollAmount = direction === 'left' ? -scrollSpeed : scrollSpeed

  scrollInterval.value = setInterval(() => {
    if (tabsHeader.value) {
      tabsHeader.value.scrollLeft += scrollAmount
      scrollOffset.value = tabsHeader.value.scrollLeft
      nextTick(checkScroll)
    }
  }, scrollDelay)
}

// 停止滚动
const stopScroll = () => {
  if (scrollInterval.value) {
    clearInterval(scrollInterval.value)
    scrollInterval.value = null
  }
}

// 单击滚动
const scrollLeft = () => {
  if (!tabsHeader.value) return
  tabsHeader.value.scrollLeft -= 100
  scrollOffset.value = tabsHeader.value.scrollLeft
  nextTick(checkScroll)
}

const scrollRight = () => {
  if (!tabsHeader.value) return
  tabsHeader.value.scrollLeft += 100
  scrollOffset.value = tabsHeader.value.scrollLeft
  nextTick(checkScroll)
}

const handleWheel = (e) => {
  if (!tabsHeader.value) return

  requestAnimationFrame(() => {
    tabsHeader.value.scrollLeft += e.deltaY
    scrollOffset.value = tabsHeader.value.scrollLeft
    checkScroll()
  })
}

// 监听标签变化
watch(() => tabs.value.length, () => {
  nextTick(checkScroll)
})

// 监听窗口大小变化
onMounted(() => {
  window.addEventListener('resize', checkScroll)
  nextTick(checkScroll)
})

onUnmounted(() => {
  window.removeEventListener('resize', checkScroll)
})

// 始化处理
onMounted(() => {
  const currentPath = router.currentRoute.value.path
  const currentRoute = router.currentRoute.value

  // 如果openTab为空，初始化它
  if (tabs.value.length === 0) {
    store.init() // 初始化store中的tabs
  }

  // 如果当前路径不在tabs中，且是有效路由，则添加它
  if (!tabs.value.find(tab => tab.path === currentPath) && currentRoute.name) {
    store.addTabs({
      name: currentRoute.name,
      path: currentPath,
      icon: currentRoute.meta?.icon || 'Document'
    })
  }

  // 设置当前活动标签
  store.setActiveIndex(currentPath)
})

// 监听路由变化
watch(() => router.currentRoute.value.path, (newPath, oldPath) => {
  if (newPath === oldPath) return

  const route = router.currentRoute.value
  // 只有当路由有name时才添加标签
  if (route.name) {
    const existingTab = tabs.value.find(tab => tab.path === newPath)
    if (!existingTab) {
      store.addTabs({
        name: route.name,
        path: newPath,
        icon: route.meta?.icon || 'Document'
      })
    }
    store.setActiveIndex(newPath)
  }
})

// 处理新增标签
const handleAdd = async () => {
  if (props.beforeAdd) {
    const canAdd = await props.beforeAdd()
    if (!canAdd) return
  }
  emit('tab-add')
}

// 修改关闭标签的逻辑
const closeTab = async (path) => {
  if (pathFilter.includes(path)) return

  if (props.beforeClose) {
    const canClose = await props.beforeClose(path)
    if (!canClose) return
  }

  if (activeTab.value === path) {
    const tabIndex = tabs.value.findIndex(item => item.path === path)
    const newPath = tabIndex > 0 ? tabs.value[tabIndex - 1].path : store.homeTab.path
    await router.push(newPath)
  }

  store.deleteTabs(path)
  emit('tab-remove', path)
}

// 修改切换标签的逻辑
const switchTab = (path) => {
  if (path === activeTab.value) return
  router.push(path)
  emit('tab-change', path)
}

// 拖拽开始
const handleDragStart = (e, index) => {
  const tab = tabs.value[index]
  if (pathFilter.includes(tab.path)) {
    e.preventDefault()
    return
  }
  draggingIndex.value = index
  e.dataTransfer.effectAllowed = 'move'
}

// 拖拽结束
const handleDragEnd = () => {
  draggingIndex.value = null
  dragOverIndex.value = null
}

// 拖拽经过
const handleDragOver = (e, index) => {
  e.preventDefault()
  // 不允许拖动到首页之前
  if (index === 0) return
  dragOverIndex.value = index
}

// 放置
const handleDrop = (e, index) => {
  e.preventDefault()
  if (draggingIndex.value === null || draggingIndex.value === index) return

  // 不允许拖动到首页之前
  if (index === 0) return

  // 不允许拖动固定标签
  if (pathFilter.includes(tabs.value[draggingIndex.value].path)) return

  store.reorderTabs(draggingIndex.value, index)

  draggingIndex.value = null
  dragOverIndex.value = null
}

// 修改右键菜单处理
const handleContextMenu = (e, tab) => {
  e.preventDefault()
  contextMenuTab.value = tab

  // 计算菜单位置，避免超出视窗
  const menuWidth = 120
  const menuHeight = 160
  const { clientX, clientY } = e
  const { innerWidth, innerHeight } = window

  contextMenuPosition.value = {
    x: clientX + menuWidth > innerWidth ? innerWidth - menuWidth : clientX,
    y: clientY + menuHeight > innerHeight ? innerHeight - menuHeight : clientY
  }

  showContextMenu.value = true

  const closeMenu = () => {
    showContextMenu.value = false
    document.removeEventListener('click', closeMenu)
  }
  document.addEventListener('click', closeMenu)
}

// 确保组件卸载时清理事件监听
onUnmounted(() => {
  document.removeEventListener('click', () => {
    showContextMenu.value = false
  })
})

// 刷新当前标签
const refreshCurrentTab = async () => {
  if (contextMenuTab.value && contextMenuTab.value.path === route.path) {
    await router.replace({
      path: '/redirect' + route.fullPath
    })
  }
  showContextMenu.value = false
}

// 关闭右键菜单选中的标签
const closeContextTab = () => {
  if (contextMenuTab.value) {
    closeTab(contextMenuTab.value.path)
  }
  showContextMenu.value = false
}

// 关闭其他标签
const closeOtherTabs = () => {
  if (contextMenuTab.value) {
    const keepTabs = tabs.value.filter(tab =>
      pathFilter.includes(tab.path) || tab.path === contextMenuTab.value.path
    )
    store.openTab = keepTabs
    if (!keepTabs.find(tab => tab.path === activeTab.value)) {
      router.push(keepTabs[0].path)
    }
  }
  showContextMenu.value = false
}

// 关闭所有可关闭的标签
const closeAllTabs = () => {
  const keepTabs = tabs.value.filter(tab => pathFilter.includes(tab.path))
  store.openTab = keepTabs
  router.push(keepTabs[0].path)
  showContextMenu.value = false
}
</script>

<style scoped>
.custom-tabs {
  display: flex;
  flex-direction: column;
  height: calc(100% - 5px);
}

.custom-tabs.border {
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
}

.custom-tabs.dark-mode {
  color: #fff;
}

.tabs-header-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--el-border-color);
  background: #f5f5f5;
}

.custom-tabs.dark-mode .tabs-header-wrapper {
  background: #1d1d1d;
}

.tabs-header {
  flex: 1;
  overflow-x: hidden;
  white-space: nowrap;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.tabs-header::-webkit-scrollbar {
  display: none;
}

.tabs-nav-wrap {
  display: inline-flex;
  padding: 2px 2px 0;
}

.tab-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0 12px;
  height: 32px;
  background: transparent;
  border: 1px solid var(--el-border-color);
  border-bottom: none;
  border-radius: 4px 4px 0 0;
  user-select: none;
  transition: all 0.3s;
  font-size: 13px;
  margin-right: 2px;
  cursor: pointer;
}

.tab-item:not(.fixed-tab) {
  cursor: pointer;
}

.tab-item:not(.fixed-tab):active {
  cursor: grabbing;
}

.tab-item.fixed-tab {
  cursor: pointer;
  background: var(--el-bg-color-page);
}

.tab-label {
  display: inline-block;
  max-width: 128px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: all 0.3s;
}

.tab-item:hover .tab-label {
  max-width: 256px;
}

.close-icon {
  margin-left: 4px;
  font-size: 11px;
  border-radius: 50%;
  padding: 2px;
  cursor: pointer;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.3s;
}

.close-icon:hover {
  background-color: var(--el-color-danger-light-7);
  color: var(--el-color-danger);
}

.close-icon:active {
  background-color: var(--el-color-danger-light-5);
  color: var(--el-color-danger);
}

.dark-mode .close-icon:hover {
  background-color: var(--el-color-danger-light-3);
  color: #fff;
}

.dark-mode .close-icon:active {
  background-color: var(--el-color-danger-light-5);
  color: #fff;
}

.tab-item.dragging {
  opacity: 0.5;
  transform: scale(1.05);
  background: var(--el-color-primary-light-8);
}

.tab-item.drag-over:not(.fixed-tab) {
  transform: translateX(2px);
  border-left: 2px solid var(--el-color-primary);
}

/* 固定标签的特殊样式 */
.fixed-tab {
  background: var(--el-bg-color-page);
}

.tab-label {
  display: inline-block;
  max-width: 128px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tab-item.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  border-color: var(--el-color-primary);
}

.scroll-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 100%;
  background: var(--el-bg-color);
  cursor: pointer;
  color: var(--el-text-color-secondary);
  transition: all 0.3s;
  user-select: none; /* 防止长按选中文本 */
}

.scroll-button:hover {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.scroll-button:active {
  background: var(--el-color-primary-light-8);
}

.dark-mode .scroll-button:hover {
  background: var(--el-color-primary-light-5);
}

.dark-mode .scroll-button:active {
  background: var(--el-color-primary-light-3);
}

.scroll-button.left {
  border-right: 1px solid var(--el-border-color);
}

.scroll-button.right {
  border-left: 1px solid var(--el-border-color);
}

.tabs-content {
  flex: 1;
  overflow: hidden;
  background: transparent;
  padding: 16px;
  position: relative;
}

.tabs-content-inner {
  position: absolute;
  top: 16px;
  left: 16px;
  right: 16px;
  bottom: 16px;
  overflow-y: auto;
  overflow-x: auto;
}

.tabs-content-inner::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.tabs-content-inner::-webkit-scrollbar-thumb {
  background: var(--el-scrollbar-bg-color);
  border-radius: 3px;
}

.tabs-content-inner::-webkit-scrollbar-track {
  background: transparent;
}

.tabs-content-inner {
  scrollbar-width: thin;
  scrollbar-color: var(--el-scrollbar-bg-color) transparent;
}

.dark-mode .tabs-content {
  background: transparent;
}

.tab-item :deep(.el-icon) {
  font-size: 14px;
}

.tab-item.closable {
  padding-right: 8px;
}

.tab-add-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  cursor: pointer;
  color: var(--el-text-color-secondary);
  transition: all 0.3s;
  border-left: 1px solid var(--el-border-color);
}

.tab-add-button:hover {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.dark-mode .tab-add-button:hover {
  background: var(--el-color-primary-light-5);
}

.tab-item.dragging {
  opacity: 0.5;
  background: var(--el-color-primary-light-8);
}

.tab-item.drag-over {
  transform: translateX(2px);
  border-left: 2px solid var(--el-color-primary);
}

.dark-mode .tab-item.dragging {
  background: var(--el-color-primary-light-3);
}

.dark-mode .tab-item.drag-over {
  border-left-color: var(--el-color-primary);
}

.scroll-button.pressing {
  background: var(--el-color-primary-light-8);
  color: var(--el-color-primary);
}

.dark-mode .scroll-button.pressing {
  background: var(--el-color-primary-light-3);
  color: #fff;
}

/* 添加全样式 */
.context-menu-box {
  background: var(--el-bg-color) !important;
  border: 1px solid var(--el-border-color) !important;
  border-radius: 4px !important;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1) !important;
  padding: 4px 0 !important;
}

.context-menu-box .el-message-box__header,
.context-menu-box .el-message-box__btns {
  display: none !important;
}

.context-menu-box .el-message-box__content {
  padding: 0 !important;
}

.context-menu-box .el-message-box__message {
  padding: 0 !important;
}

.context-menu-item {
  padding: 8px 16px;
  cursor: pointer;
  font-size: 14px;
  color: var(--el-text-color-primary);
  transition: all 0.3s;
}

.context-menu-item:hover {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.dark-mode .context-menu-item:hover {
  background: var(--el-color-primary-light-3);
  color: #fff;
}

.el-dropdown {
  display: none;
}

.el-dropdown.el-popper {
  display: block;
}

.context-menu {
  position: fixed;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0,0,0,0.1);
  padding: 4px 0;
  min-width: 120px;
  z-index: 3000;
}

.context-menu-item {
  padding: 8px 16px;
  cursor: pointer;
  font-size: 14px;
  color: var(--el-text-color-primary);
  transition: all 0.3s;
}

.context-menu-item:hover {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.dark-mode .context-menu-item:hover {
  background: var(--el-color-primary-light-3);
  color: #fff;
}
</style>
