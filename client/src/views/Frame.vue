// noinspection JSCheckFunctionSignatures

<!--suppress JSUnresolvedReference -->
<script setup>
import { useRouter } from "vue-router";
import {computed} from "vue";
import SubMenu from "@/components/framework/subMenu.vue";
import {collapseStore} from "@/store/index.js";
import Navexpbtn from "@/components/framework/navExBtn.vue";
import BreadCrumb from "@/components/framework/breadCrumb.vue";
import ThemeOption from "@/components/framework/ThemeOption.vue";
import UserProfile from '@/components/framework/userProfile.vue';
import CustomTabs from '@/components/framework/CustomTabs.vue'
import { tabStore } from '@/store'


const appEnv = import.meta.env;
const collapse = collapseStore();
const router = useRouter();
const routes = router.getRoutes();
const isCollapse = computed(() => collapse.isCollapse);
const defaultActive = computed(() => router.currentRoute.value.path);
const store = tabStore()
const openTab = computed(() => store.openTab)
const filteredRoutes = computed(() => {
  return routes.filter(route => route.meta && !route.meta["hidden"]);
});

function toggleCollapse() {
  collapse.toggleCollapse();
}


</script>
<template>
  <el-container class="MainView">
    <!--  左侧导航栏  -->
    <el-aside width="auto" class="MainAside">
      <el-menu :default-active="defaultActive" popper-class="menu-popper" :collapse="isCollapse" router>
        <span v-if="!isCollapse" class="main-nav-title">{{appEnv['VITE_APP_TITLE']}}</span>
        <div v-else class="main-nav-title" style="padding: 14px">
          <img src="/favicon.svg" alt="favicon" width="32" height="32" />
        </div>
        <!--suppress JSValidateTypes -->
        <sub-menu :menu="menu" v-for="menu in filteredRoutes" :key="menu.path" />
      </el-menu>
    </el-aside>
    <!----------------->
    <!--  主体内容  -->
    <el-container>
      <!--   顶部组件   -->
      <el-header class="MainHeader">
        <div class="header-bar-left">
          <navexpbtn class="nav_ex_btn" :is-collapse="isCollapse" :onToggleClick="toggleCollapse" /> <!-- 侧边栏折叠按钮 -->
          <bread-crumb /> <!-- 面包屑 -->
        </div>
        <div class="header-bar-right">
          <theme-option />
          <user-profile />
        </div>
      </el-header>
      <!--   tab标签页与路由界面   -->
      <div class="main-content">
        <custom-tabs class="tabs">
          <router-view v-slot="{ Component }">
            <keep-alive :include="openTab.map(tab => tab.component)">
              <component
                :is="Component"
                :key="$route.fullPath"
              />
            </keep-alive>
          </router-view>
        </custom-tabs>
      </div>


      <el-footer class="footer">
        {{ appEnv['VITE_APP_COPYRIGHT'] }}
      </el-footer>
    </el-container>
  </el-container>
</template>

<style scoped>
@import "@/styles/Frame.css";
</style>
