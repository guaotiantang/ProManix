<script setup>
  import {useRouter} from "vue-router";
  import {ref, watch} from "vue";
  const router = useRouter();
  const breadArr = ref(["首页"]);
  watch(router.currentRoute, (to) => {
    refreshBreadArr(to.path);
  });

  function refreshBreadArr(path) {
    breadArr.value = [];
    const pathArr = path.split("?")[0].split("/");
    let pathStr = "";
    for (let i = 1; i < pathArr.length; i++) {
      pathStr += "/" + pathArr[i];
      const route = router.getRoutes().find(route => route.path.split(":")[0] === pathStr);
      if (route) {
        breadArr.value.push(route.name);
      }
    }
  }

</script>

<template>
  <div class="breadcrumb_box">
    <el-breadcrumb separator="/">
      <el-breadcrumb-item v-for="(item) in breadArr" >{{ item }}</el-breadcrumb-item>
    </el-breadcrumb>
  </div>
</template>

<style scoped>
  .breadcrumb_box {
    display: flex;
    align-items: center;
  }
</style>
