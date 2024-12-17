<script lang="ts" setup>
import { ref, onMounted } from 'vue';
const imgRef = ref<HTMLImageElement | null>(null);
onMounted(() => {
  if (imgRef.value) {
    imgRef.value.onload = () => {
      imgRef.value?.setAttribute("class", "transform-in");
    };
  }
});
</script>

<template>

  <div class="load-main">
    <img src="/favicon.svg" alt="ProManix" ref="imgRef" />
    <el-progress :percentage="100" :stroke-width="15" :show-text="false" striped striped-flow :duration="10" />
    <span class="load-text">Loading...</span>
  </div>

</template>

<!--suppress CssUnusedSymbol -->
<style scoped>
  .load-main .el-progress--line {
    margin-bottom: 32px;
    width: 512px;
  }
  .load-main{
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    height: 95vh;
  }
  @keyframes bounce-in {
    0% {
      transform: scale(0);
    }
    50% {
      opacity: 0.5;
    }
    100% {
      transform: scale(1);
      opacity: 1;
    }
  }
  .transform-in {
    opacity: 0;
    animation: bounce-in 1s ease-in-out forwards;
  }

  @keyframes load-text {
    0% {
      opacity: 0;
    }
    50% {
      opacity: 0.5;
    }
    100% {
      opacity: 1;
    }
  }
  .load-text {
    animation: load-text 3s infinite;

  }


</style>
