<!--suppress JSUnresolvedReference -->
<template>
  <el-container style="padding: 20px">
    <!-- 侧边栏 -->
    <el-aside style="width: auto">
      <el-card class="profile-card">
        <div class="profile-header">
          <img 
            :src="userInfo.Avatar"
            alt="头像" 
            class="profile-avatar" 
          />
          <avatarDialog 
            ref="imageCropperRef" 
            @callback="avatarCallback" 
            :imgUrl="userInfo.Avatar"
            title="修改头像"
          ></avatarDialog>
        </div>
        <div class="profile-info">
          <p>
            <el-icon :size="18"><component :is="icons['BiSolidUser']" /></el-icon>
            <span class="card-title">UID</span>
            <span class="card-value">{{ userInfo.ID }}</span>
          </p>
          <p>
            <el-icon :size="18"><component :is="icons['BiSolidUserCircle']" /></el-icon>
            <span class="card-title">用户名</span>
            <span class="card-value">{{ userInfo.UserName }}</span>
          </p>
          <p>
            <el-icon :size="18"><component :is="icons['AiOutlineMail']" /></el-icon>
            <span class="card-title">邮箱地址</span>
            <span class="card-value">{{ userInfo.Email }}</span>
          </p>
          <p>
            <el-icon :size="18"><component :is="icons['BiTime']" /></el-icon>
            <span class="card-title">创建时间</span>
            <span class="card-value">{{ userInfo.CreateTime }}</span>
          </p>
        </div>
      </el-card>
    </el-aside>

    <!-- 主内容 -->
    <el-main style="border: lightgray solid 1px">
      <el-tabs v-model="UserProfileActiveTab">
        <el-tab-pane label="基本资料" name="info">
          <el-form :model="editUser" label-width="80px" class="edit-form">
            <el-form-item label="用户名">
              <el-input v-model="editUser.UserName" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="editUser.Email" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="saveUserInfo">保存</el-button>
              <el-button @click="resetUserInfo">重置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="修改密码" name="password">
          <el-form :model="passwordForm" label-width="80px" class="edit-form">
            <el-form-item label="新密码">
              <el-input v-model="passwordForm.newPassword" type="password" />
            </el-form-item>
            <el-form-item label="确认密码">
              <el-input v-model="passwordForm.confirmPassword" type="password" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="changePassword">保存</el-button>
              <el-button @click="resetPasswordForm">重置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-main>
  </el-container>


</template>

<script setup>
import { reactive, onMounted, ref, computed } from "vue";
import { Info, UpdateUser, UpdateAvatar } from "@/apis/Sys/user";
import { icons, showMsg } from "@/libs/Utils.js";
import { userInfoStore, UserProfileActiveTab } from "@/store";
import avatarDialog from "@/components/framework/AvatarDialog.vue";

const imageCropperRef = ref(null)
// 用户信息
const store = userInfoStore();
const userInfo = computed({
  get: () => store.userInfo,
  set: (newValue) => store.setUserInfo({...newValue})
});


const avatarCallback = async (base64) => {
  const avatarUrl = await UpdateAvatar(base64);
  if (avatarUrl) {
    userInfo.value.Avatar = avatarUrl;
  }
}


// editUser 也相应修改
const editUser = reactive({...userInfo.value});

// 密码表单
const passwordForm = reactive({
  newPassword: "",
  confirmPassword: "",
});

// 加载用户信息
const loadUserInfo = async () => {
  await Info();
  Object.assign(editUser, userInfo.value);
};

// 保存用户信息
const saveUserInfo = async () => {
  await UpdateUser(editUser);
  await loadUserInfo();
};

// 修改密码
const changePassword = async () => {
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    await showMsg("两次输入的密码不一致", "error");
    return;
  }else if (passwordForm.newPassword === "") {
    await showMsg("密码不能为空", "error");
    return;
  }
  try {
    await UpdateUser({ newPassword: passwordForm.newPassword });
  } finally {
    resetPasswordForm();
  }
};

// 更新头像信息
// 重置表单
const resetUserInfo = () => Object.assign(editUser, userInfo.value);
const resetPasswordForm = () => {
  passwordForm.newPassword = "";
  passwordForm.confirmPassword = "";
};

// 页面加载时加载用户信息
onMounted(loadUserInfo);
</script>
<style scoped>
/* 样式 */
.card-title {
  margin-left: 10px;
  text-align: left;
  width: 80px;
}
.card-value {
  flex: 1;
  text-align: right;
}
.profile-card {
  text-align: center;
  padding: 20px;
}

.profile-avatar {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  margin-bottom: 10px;
  cursor: pointer;
}

.profile-info p {
  margin: 5px 0;
  font-size: 14px;
  color: #666;
  display: flex;
  align-items: center;
}


.edit-form {
  max-width: 400px;
  margin: 20px auto;
}


</style>
