<script setup lang="ts">
// @ts-ignore
  import { icons } from "@/libs/Utils.js";


  interface Menu {
    path: string
    name: string
    meta: {
      hidden: boolean
      icon: string
    }
    children?: Menu[] | undefined
  }


  defineProps<{
    menu: Menu
  }>()

</script>

<template>
  <el-sub-menu :index="menu.name" v-if="menu.children && menu.children.length > 0">
    <template #title>
      <el-icon><component :is="icons[menu.meta.icon]" /></el-icon>
      <span>{{ menu.name }}</span>
    </template>
    <sub-menu :menu="menuItem" v-for="menuItem in menu.children" :key="menuItem.path"></sub-menu>
  </el-sub-menu>
  <el-menu-item :index="menu.path" @click="" v-else>
    <el-icon v-if="menu.meta.icon"><component :is="icons[menu.meta.icon]" /></el-icon>
    <template #title>{{ menu.name }}</template>
  </el-menu-item>
</template>

<style scoped>

</style>
