<!--suppress JSUnresolvedReference -->
<template>
  <div>
    <div class="edit-avatar" @click="openUpload">修改头像</div>
    <!-- 上传弹窗 -->
    <el-dialog v-model="uploadDialog" :title="title" width="680" :before-close="handleClose">
      <div class="container">
        <!-- 左侧裁剪区 -->
        <div class="left">
          <!-- 大图显示区 -->
          <div class="big-image-preview">
            <img v-if="imgUrl" :src="imgUrl" class="big-image circle" ref="imageRef" alt="" />
            <div v-else class="big-image" @click="chooseImage" />
          </div>
          <div class="tool">
            <p>{{ tips }}</p>
            <el-button size="default" @click="chooseImage" type="primary">选择图片</el-button>
            <el-button size="small" @click="zoomImage(0.2)">放大</el-button>
            <el-button size="small" @click="zoomImage(-0.2)">缩小</el-button>
            <el-button size="small" @click="rotateImage(90)">左转90°</el-button>
            <el-button size="small" @click="rotateImage(90)">右转90°</el-button>
          </div>
        </div>
        <!-- 右侧预览区 -->
        <div class="right">
          <!-- 小图预览区域 -->
          <div class="right-top">
            <div class="image-view circle"></div>
          </div>
        </div>
      </div>
      <!-- 只用input来实现上传，但是不显示input -->
      <input v-show="false" ref="fileRef" type="file" accept="image/png, image/jpeg" @change="getImageInfo" />
      <template #footer>
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="submitImage">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import 'cropperjs/dist/cropper.css'
import Cropper from 'cropperjs'
import { ElMessage } from 'element-plus'

const props = defineProps({
  imgUrl: { // 回显需求
    type: String,
    default: ''
  },
  title: { //弹框标题
    type: String,
    default: '修改头像'
  },
  tips: {  //图片下的提示语
    type: String,
    default: ''
  },
  api: { //上传的api
    type: String,
    default: '/api/apps/common/Index/file'
  },
  size: {  //允许上传最大图片MB
    type: Number,
    default: 3
  }
})
// 默认显示的图片
const imgUrl = ref(props.imgUrl)
const tips = ref(props.tips)
const isCreate = ref(false)
// 裁剪对象
const cropper = ref(null)
const title = ref(props.title)
const size = ref(props.size)
const info = ref()
const imageRef = ref(null)
const cropperHeight = ref()
const cropperWidth = ref()
const uploadDialog = ref(false)
const fileRef = ref(null)
const fileName = ref()
const emit = defineEmits(['callback'])
// 打开弹窗方法
const openUpload = () => {
  try {
    // 清除所有内容，重新选择图片
    if (isCreate.value || imgUrl.value) {
      cropper.value.destroy()
      isCreate.value = false
      imgUrl.value = ''
    }
  }finally{
    uploadDialog.value = true
  }

}

// 关闭弹窗
const handleClose = () => {
  uploadDialog.value = false
}
// 选择图片
const chooseImage = () => {
  // 当input的type属性值为file时，点击方法可以进行选取文件
  fileRef.value.click()
}
// 确定按钮
const submitImage = () => {
  if (!cropper.value || !imgUrl.value) {
    ElMessage.warning('请选择图片')
    return
  }

  const cas = cropper.value.getCroppedCanvas()
  const base64url = cas.toDataURL('image/jpeg')
  cas.toBlob(function (e) {
    imgUrl.value = window.URL.createObjectURL(e)
  })
  info.value = cropper.value.getData()
  uploadDialog.value = false
  emit('callback', base64url, info.value)
}

// 获取文件信息
const getImageInfo = (e) => {
  // 上传的文件
  const file = e.target.files[0]
  if (!file) return;
  const fileSize = (file.size / 1024).toFixed(2)
  if (fileSize > size.value * 1024) {
    ElMessage.warning(`'图片大小必须在${size.value}MB以内！'`)
    return false
  }
  fileName.value = file.name
  // 获取 window 的 URL 工具
  const URL = window.URL || window.webkitURL
  // 通过 file 生成目标 url
  imgUrl.value = URL.createObjectURL(file)
  nextTick(() => {
    // 判定裁剪对象是否存在
    // 存在销毁重新创建（这里不替换图片，图片不一样大时会变形），不存在创建对象
    if (cropper.value) {
      cropper.value.destroy()
      cropImage()
    } else {
      cropImage()
    }
    isCreate.value = true
  })
}
// 裁剪图片
const cropImage = () => {
  if (imageRef.value) {
    cropper.value = new Cropper(imageRef.value, {
      // 宽高比
      aspectRatio: 1, //设置裁剪框为固定的宽高比为1，即正方形
      viewMode: 1,
      // 预览
      preview: '.image-view',
      background: false,
      crop(event) {
        cropperHeight.value = event.detail.height
        cropperWidth.value = event.detail.width
      }
    })
    isCreate.value = true
  }
}
// 旋转
const rotateImage = (angle) => {
  if (isCreate.value) {
    cropper.value.rotate(angle)
  }
}
// 缩放
const zoomImage = (num) => {
  if (isCreate.value) {
    cropper.value.zoom(num)
  }
}

</script>

<style scoped lang="scss">
//上传的基本样式
.upload {
  width: 142px;
  height: 142px;
  // border: 5px solid #eeeeee;
  box-sizing: border-box;
  cursor: pointer;
  background-size: 100%;
  border-radius: 6px;
  background: #eee center center;
}

//hover的基本样式
.base-hover {
  position: absolute;
  width: 100%;
  height: 100%;
  content: '更换头像';
  background: black;
  color: #ffffff;
  display: flex;
  justify-content: center;
  align-items: center;
  opacity: 0.6;
}

.container {
  width: 600px;
  height: 400px;
  display: flex;
  margin: 20px 20px 0;
  .left {
    width: 65%;
    height: 100%;
    .big-image-preview {
      width: 100%;
      height: 85%;
      background-size: 100% 100%;
      background-repeat: no-repeat;
      background-position: center center;
      border: 1px solid #999;
    }
    .tool {
      width: 100%;
      height: 15%;
      font-size: 10px;
      display: flex;
      justify-content: center;
      align-items: center;
      span {
        margin: 0 10px;
        cursor: pointer;
      }
    }
    .big-image {
      width: 100%;
      height: 100%;
      display: block;
      max-width: 100%;
      border-radius: 50%;
    }
  }
  .right {
    width: 240px;
    height: 100%;
    font-size: 14px;
    .right-top {
      width: 100%;
      height: 70%;
      display: flex;
      flex-direction: column;
      align-items: center;
      .image-view {
        margin-top: 30%;
        margin-left: 30px;
        overflow: hidden;
        min-width: 200px;
        height: 200px;
        border-radius: 50%;
      }
      .view-info {
        position: absolute;
        top: 340px;
      }
    }
    .right-bottom {
      width: 100%;
      height: 30%;
      display: flex;
      flex-direction: column-reverse;
      align-items: center;
    }
  }
}
.el-icon :deep(.avatar-uploader-icon) {
  font-size: 28px;
  color: #8c939d;
  width: 142px;
  height: 142px;
  text-align: center;
  border: 1px dashed var(--el-border-color);
  border-radius: 6px;
}
:deep(.cropper-point.point-se) {
  height: 5px;
  width: 5px;
}
.edit-avatar {
  color: #409eff;
  cursor: pointer;
  font-size: 14px;
}
</style>

