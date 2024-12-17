<!--suppress ES6PreferShortImport -->
<script setup lang="ts">
import DarkIcon from "../../assets/icons/icon-Dark.vue";
import LightIcon from "../../assets/icons/icon-Light.vue";
import { themeStore } from "../../store/index.js";
import { PropType } from "vue";
const theme = themeStore();
// 定义 prop，限制 placement 为有效的值
defineProps({
  tipPlacement: {
    type: String as PropType<
        "top" | "top-start" | "top-end" | "bottom" | "bottom-start" | "bottom-end" |
        "left" | "left-start" | "left-end" | "right" | "right-start" | "right-end"
    >,
    default: "top",
  },
});
</script>

<template>
  <el-tooltip content="切换主题" :placement="tipPlacement">
    <el-switch
        v-model="theme.isDark"
        @change="theme.toggleTheme()"
        :active-action-icon="DarkIcon"
        :inactive-action-icon="LightIcon"
    />
  </el-tooltip>
</template>

<style scoped>
</style>
