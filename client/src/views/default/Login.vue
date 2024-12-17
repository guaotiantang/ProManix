<!--suppress JSUnresolvedReference -->
<script setup>
import { ref } from 'vue';
import ThemeOption from '@/components/framework/ThemeOption.vue';
import { RegisterUser, LoginUser } from '@/apis/Sys/User.js';
import { isLogin } from '@/store';
import {useRouter} from "vue-router";
const router = useRouter();
const loginLoad = ref(false);
const appEnv = import.meta.env;
const loginInfo = ref({
  Email: '',
  Password: '',
});
const registerInfo = ref({
  Email: '',
  UserName: '',
  Password: '',
  confirm: '',
});
const viewStatus = ref('login');

// 登录方法
async function handleLogin() {
  if (await LoginUser(loginInfo.value)){
    isLogin.value = true;
    await router.push('/');
  }
}

// 注册方法
async function handleRegister() {
  if (await RegisterUser(registerInfo.value)){
   viewStatus.value = 'login';
   loginInfo.value.Email = registerInfo.value.Email;
    loginInfo.value.Password = registerInfo.value.Password;
  }
}
</script>

<template>
  <el-container class="mainView" v-loading="loginLoad">
    <span class="loginTitle">{{ appEnv.VITE_APP_TITLE }}</span>

    <!-- 登录页面 -->
    <div class="boxView" v-if="viewStatus === 'login'">
      <span class="boxTitle">Login</span>

      <!-- 表单默认提交时触发 handleLogin -->
      <el-form
          style="margin-top: 32px;"
          label-position="left"
          label-width="48px"
          size="large"
          @submit.prevent="handleLogin"
      >
        <el-form-item label="邮箱">
          <el-input v-model="loginInfo.Email" placeholder="Email"></el-input>
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="loginInfo.Password" placeholder="Password" show-password></el-input>
        </el-form-item>
        <el-form-item style="padding-left: 39px; margin-top: 32px">
          <el-button type="primary" size="large" native-type="submit">Login</el-button>
        </el-form-item>
      </el-form>

      <el-footer class="boxFooter">
        <div style="width: 50%; justify-content: center;">
          <themeOption tipPlacement="top" />
        </div>
        <div style="width: 50%; display: flex; flex-direction: row; justify-content: flex-end">
          <el-tooltip content="注册" placement="top">
            <el-button link type="primary" size="large" style="font-size: 1rem" @click="viewStatus = 'reg'">Register</el-button>
          </el-tooltip>
        </div>
      </el-footer>
    </div>

    <!-- 注册页面 -->
    <div class="boxView" v-else>
      <span class="boxTitle">Register</span>

      <!-- 表单默认提交时触发 handleRegister -->
      <el-form
          style="margin-top: 16px;"
          label-position="right"
          label-width="72px"
          size="large"
          @submit.prevent="handleRegister"
      >
        <el-form-item label="邮箱">
          <el-input v-model="registerInfo.Email" placeholder="Email"></el-input>
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="registerInfo.UserName" placeholder="Username"></el-input>
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="registerInfo.Password" placeholder="Password" show-password></el-input>
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input v-model="registerInfo.confirm" placeholder="ConfirmPassword" show-password></el-input>
        </el-form-item>
        <el-form-item style="padding-left: 18px; margin-top: 32px">
          <el-button type="primary" size="large" native-type="submit">Register</el-button>
        </el-form-item>
      </el-form>

      <el-footer class="boxFooter">
        <div style="width: 50%; justify-content: center;">
          <themeOption tipPlacement="top" />
        </div>
        <div style="width: 50%; display: flex; flex-direction: row; justify-content: flex-end">
          <el-tooltip content="登录" placement="top">
            <el-button link type="primary" size="large" style="font-size: 1rem" @click="viewStatus = 'login'">Login</el-button>
          </el-tooltip>
        </div>
      </el-footer>
    </div>
  </el-container>
</template>

<style scoped>

  .mainView {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    height: 100vh;
    width: 100vw;
  }
  .boxView {
    width: 512px;
    height: auto;
    display: flex;
    flex-direction: column;
    align-items: center;
    box-shadow: 0 0 15px rgba(0, 0, 0, 0.5);
  }
  .loginTitle, .boxTitle {
    font-family: 'TypoGraphica', 'argon', 'Arial Narrow', serif;
    font-size: 3em;
    letter-spacing: 2px;
    background: linear-gradient(120deg, grey, cornflowerblue, coral, darkgoldenrod);
    background-clip: text;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    color: transparent;
  }

  .boxFooter {
    display: flex;
    flex-direction: row;
    width: 100%;
    padding: 10px;
    font-size: 12px;
    margin-top: auto;
  }
</style>
