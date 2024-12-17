<template>
  <div class="page">
    <img class="fade" src="@/assets/images/404.png" alt="404">
    <div class="tips">
      <h1>温馨提示：您访问的地址不存在！</h1>
      <p>你正在寻找的页面无法找到。</p>
      <a href="#" @click.prevent="goBack">返回上一个页面</a>
      <a class="link" href="/">返回首页</a>
    </div>
  </div>
</template>

<script>
export default {
  name: 'My404Page',
  methods: {
    goBack() {
      window.history.back();
    }
  },
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
}

.tips {
  margin-top: 20px;
  text-align: center;

}

h1 {
  font-size: 24px;
}

p {
  text-shadow: 0 1px 2px white;
  font-weight: 200;
  text-align: center;
}

a {
  color: #409eff;
  text-decoration: none;
  margin: 10px;
  text-align: center;
  display: block;
}


</style>
