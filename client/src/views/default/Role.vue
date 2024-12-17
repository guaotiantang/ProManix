<template>
    <div class="permission-config">
      <el-card>
        <!-- 角色管理部分 -->
        <div class="role-header">
          <h3>角色权限配置</h3>
          <el-button type="primary" @click="handleAddRole">新增角色</el-button>
        </div>
  
        <el-table :data="roleList" border style="width: 100%">
          <el-table-column prop="name" label="角色名称" width="180" />
          <el-table-column prop="description" label="角色描述" />
          <el-table-column label="操作" width="250">
            <template #default="{ row }">
              <el-button type="primary" @click="handleConfigPermission(row)">配置权限</el-button>
              <el-button type="warning" @click="handleEditRole(row)">编辑</el-button>
              <el-button type="danger" @click="handleDeleteRole(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
  
      <!-- 角色表单弹窗 -->
      <el-dialog
        v-model="roleDialog.visible"
        :title="roleDialog.type === 'add' ? '新增角色' : '编辑��色'"
        width="500px"
      >
        <el-form
          ref="roleFormRef"
          :model="roleForm"
          :rules="roleRules"
          label-width="80px"
        >
          <el-form-item label="角色名称" prop="name">
            <el-input v-model="roleForm.name" placeholder="请输入角色名称" />
          </el-form-item>
          <el-form-item label="角色描述" prop="description">
            <el-input
              v-model="roleForm.description"
              type="textarea"
              placeholder="请输入角色描述"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="roleDialog.visible = false">取消</el-button>
          <el-button type="primary" @click="submitRoleForm">确定</el-button>
        </template>
      </el-dialog>
  
      <!-- 权限配置弹窗 -->
      <el-dialog
        v-model="permissionDialog.visible"
        title="配置权限"
        width="600px"
      >
        <el-tree
          ref="permissionTreeRef"
          :data="permissionList"
          show-checkbox
          node-key="id"
          :props="{ 
            label: 'name',
            children: 'children'
          }"
          :default-checked-keys="selectedPermissions"
        />
        <template #footer>
          <el-button @click="permissionDialog.visible = false">取消</el-button>
          <el-button type="primary" @click="submitPermissions">确定</el-button>
        </template>
      </el-dialog>
    </div>
  </template>
  
  <script setup>
  import { ref, reactive } from 'vue'
  import {showMsg} from '@/libs/Utils.js'
  
  // 角色列表
  const roleList = ref([])
  // 权限树数据
  const permissionList = ref([])
  
  // 角色表单相关
  const roleFormRef = ref()
  const roleForm = reactive({
    id: '',
    name: '',
    description: ''
  })
  const roleRules = reactive({
    name: [{ required: true, message: '请输入角色名称', trigger: 'blur' }]
  })
  
  // 弹窗控制
  const roleDialog = reactive({
    visible: false,
    type: 'add'
  })
  const permissionDialog = reactive({
    visible: false,
    currentRole: null
  })
  
  // 选中的权限
  const selectedPermissions = ref([])
  const permissionTreeRef = ref()
  
  // 获取角色列表
  const getRoleList = async () => {
    try {
      const res = await fetch('/api/roles')
      roleList.value = await res.json()
    } catch (error) {
      showMsg('获取角色列表失败', 'error')
    }
  }
  
  // 获取权限列表
  const getPermissionList = async () => {
    try {
      const res = await fetch('/api/permissions')
      permissionList.value = await res.json()
    } catch (error) {
      showMsg('获取权限列表失败', 'error')
    }
  }
  
  // 新增角色
  const handleAddRole = () => {
    roleDialog.type = 'add'
    roleDialog.visible = true
    roleForm.id = ''
    roleForm.name = ''
    roleForm.description = ''
  }
  
  // 编辑角色
  const handleEditRole = (row) => {
    roleDialog.type = 'edit'
    roleDialog.visible = true
    roleForm.id = row.id
    roleForm.name = row.name
    roleForm.description = row.description
  }
  
  // 删除角色
  const handleDeleteRole = (row) => {
    showMsg('确认删除该角色吗？', 'warning').then(async () => {
      try {
        await fetch(`/api/roles/${row.id}`, { method: 'DELETE' })
        showMsg('删除成功', 'success')
        getRoleList()
      } catch (error) {
        showMsg('删除失败', 'error')
      }
    })
  }
  
  // 提交角色表单
  const submitRoleForm = async () => {
    if (!roleFormRef.value) return
    await roleFormRef.value.validate(async (valid) => {
      if (valid) {
        try {
          const url = roleDialog.type === 'add' ? '/api/roles' : `/api/roles/${roleForm.id}`
          const method = roleDialog.type === 'add' ? 'POST' : 'PUT'
          await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(roleForm)
          })
          showMsg(`${roleDialog.type === 'add' ? '新增' : '编辑'}成功`, 'success')
          roleDialog.visible = false
          getRoleList()
        } catch (error) {
          showMsg(`${roleDialog.type === 'add' ? '新增' : '编辑'}失败`, 'error')
        }
      }
    })
  }
  
  // 配置权限
  const handleConfigPermission = (row) => {
    permissionDialog.visible = true
    permissionDialog.currentRole = row
    selectedPermissions.value = row.permissions.map(p => p.id)
  }
  
  // 提交权限配置
  const submitPermissions = async () => {
    if (!permissionDialog.currentRole) return
    try {
      const checkedKeys = permissionTreeRef.value.getCheckedKeys()
      await fetch(`/api/roles/${permissionDialog.currentRole.id}/permissions`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ permissionIds: checkedKeys })
      })
      showMsg('权限配置成功', 'success')
      permissionDialog.visible = false
      getRoleList()
    } catch (error) {
      showMsg('权限配置失败', 'error')
    }
  }
  
  // 初始化
  getRoleList()
  getPermissionList()
  </script>
  
  <style scoped>
  .permission-config {
    padding: 20px;
  }
  .role-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }
  </style>