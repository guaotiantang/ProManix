
<!--suppress JSUnresolvedReference -->
<script setup>
  import Frame from "@/views/Frame.vue";

  const appEnv = import.meta.env;
  document.title = appEnv.VITE_APP_TITLE;
  import LoadPage from '@/views/default/LoadPage.vue';
  import {onMounted, ref} from "vue";
  import {Info, CheckCookie} from "@/apis/Sys/User.js";
  import Login from "@/views/default/Login.vue";
  import {useRouter} from "vue-router";
  import { themeStore, isLogin } from "@/store";

  const router = useRouter();
  const showLoadView = ref(true);
  onMounted(async() => {
    themeStore().initTheme(); // 初始化主题
    showLoadView.value = true;
    if (await CheckCookie()){
      const info = await Info();
      isLogin.value = info !== null;
    }else {
      isLogin.value = false;
    }
    // 如果未登录，判断当前路由是否为/，如果不是则跳转到登录页
    if (!isLogin.value && router.currentRoute.value.path !== '/login') {
      await router.push('/login');
      await new Promise(resolve => setTimeout(resolve, 2000)); // 延迟2秒
    }
    showLoadView.value = false;
  })
</script>

<template>
  <LoadPage v-if="showLoadView" />
  <el-container v-else style="height: 100vh">
    <Login v-if="!isLogin" />
    <Frame v-else />
  </el-container>
  <footer v-if="showLoadView || !isLogin" class="footer">{{ appEnv.VITE_APP_COPYRIGHT }}</footer>
</template>

<style scoped>
@import "styles/App.css";

</style>
