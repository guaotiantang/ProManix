<template>
  <div style="padding: 0 0 0 15px; display: flex; align-items: center" @click="toggleClick">
    <svg
        :class="{'is-active': !isActive, 'dark-mode': isDark}"
        class="navexpbtn"
        viewBox="0 0 1024 1024"
        xmlns="http://www.w3.org/2000/svg"
        width="64"
        height="64"
    >
      <!-- SVG 内容 -->
      <path
          d="M408 442h480c4.4 0 8-3.6 8-8v-56c0-4.4-3.6-8-8-8H408c-4.4 0-8 3.6-8
           8v56c0 4.4 3.6 8 8 8zm-8
           204c0 4.4 3.6 8 8 8h480c4.4 0 8-3.6 8-8v-56c0-4.4-3.6-8-8-8H408c-4.4
           0-8 3.6-8
           8v56zm504-486H120c-4.4 0-8 3.6-8
           8v56c0 4.4 3.6 8 8
           8h784c4.4 0 8-3.6
           8-8v-56c0-4.4-3.6-8-8-8zm0
           632H120c-4.4 0-8 3.6-8
           8v56c0 4.4 3.6 8 8
           8h784c4.4 0 8-3.6
           8-8v-56c0-4.4-3.6-8-8-8zM142.4
           642.1L298.7 519a8.84 8.84 0 0 0
           0-13.9L142.4 381.9c-5.8-4.6-14.4-.5-14.4
           6.9v246.3a8.9 8.9 0 0 0 14.4 7z"
      />
    </svg>
  </div>
</template>

<script setup>
import { useDark } from '@vueuse/core'
import { computed } from 'vue'

const props = defineProps({
  isCollapse: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['toggleClick'])

const isDark = useDark()
const isActive = computed(() => props.isCollapse)

function toggleClick() {
  emit('toggleClick')
}
</script>

<style scoped>
.navexpbtn {
  display: inline-block;
  vertical-align: middle;
  width: 20px;
  height: 20px;
  transition: transform 0.3s ease;
  cursor: pointer;
  fill: black; /* 默认图标颜色 */
}

.navexpbtn.is-active {
  transform: rotate(180deg);
}

.navexpbtn.dark-mode {
  fill: white; /* Dark 模式下，图标变为白色 */
}
</style>
