<!--suppress CssUnusedSymbol -->
<script setup>
import {computed} from 'vue';
import {useRouter} from 'vue-router';
import {userInfoStore, UserProfileActiveTab} from '@/store/index.js';
import {LogoutUser} from '@/apis/Sys/User.js';
import {icons} from '@/libs/Utils.js';

const userInfo = computed(() => userInfoStore().userInfo);
const router = useRouter();

const handleCommand = (command) => {
  switch (command) {
    case 'profile':
      UserProfileActiveTab.value = 'info';
      router.push('/sys/profile');
      break;
    case 'password':
      UserProfileActiveTab.value = 'password';
      router.push('/sys/profile');
      break;
    case 'logout':
      LogoutUser();
      break;
  }
};

const avatarSrc = computed(() => {
  return userInfo.value.Avatar || '/assets/images/user.svg'
});
</script>

<template>
  <div class="dropdown-container">
    <el-popover
        :width="120"
        trigger="hover"
        placement="bottom-end"
        popper-class="user-menu-popover"
    >
      <template #reference>
        <div class="avatar-box" tabindex="0">
          <el-avatar class="avatarBtn" :src="avatarSrc" />
          <el-text type="primary">{{ userInfo.UserName }}</el-text>
        </div>
      </template>

      <div class="user-menu-list">
        <button class="menu-item" @click="handleCommand('profile')">
          <el-icon><component :is="icons['BiSolidUser']" /></el-icon>
          <span>个人中心</span>
        </button>
        <button class="menu-item" @click="handleCommand('password')">
          <el-icon><component :is="icons['BiSolidLock']" /></el-icon>
          <span>修改密码</span>
        </button>
        <div class="divider"></div>
        <button class="menu-item" @click="handleCommand('logout')">
          <el-icon><component :is="icons['BiSolidLogOut']" /></el-icon>
          <span>退出</span>
        </button>
      </div>
    </el-popover>
  </div>
</template>

<style scoped>
.user-menu-list {
  padding: 4px 0;
}

.menu-item {
  width: 100%;
  border: none;
  background: none;
  text-align: left;
  display: flex;
  align-items: center;
  padding: 8px 16px;
  cursor: pointer;
  transition: background-color 0.3s;
}

.menu-item:hover {
  background-color: var(--el-color-primary-light-9);
}

.menu-item .el-icon {
  margin-right: 8px;
  font-size: 16px;
}

.divider {
  margin: 4px 0;
  border-top: 1px solid var(--el-border-color-lighter);
}

.avatar-box {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 2px 8px;
  border-radius: 4px;
}

.avatar-box .el-text {
  margin-left: 8px;
}
</style>
