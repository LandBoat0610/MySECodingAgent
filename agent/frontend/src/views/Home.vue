<template>
  <div class="home">
    <el-container>
      <el-header class="header">
        <div class="logo">
          <el-icon size="24"><Monitor /></el-icon>
          <span>Code Agent</span>
        </div>
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新建项目
        </el-button>
      </el-header>
      
      <el-main class="main">
        <div class="projects-container">
          <h2>项目列表</h2>
          
          <el-empty v-if="!hasProjects" description="暂无项目，点击右上角创建">
            <el-button type="primary" @click="showCreateDialog = true">创建项目</el-button>
          </el-empty>
          
          <el-row v-else :gutter="20">
            <el-col :span="8" v-for="project in projects" :key="project.id">
              <el-card class="project-card" shadow="hover" @click="goToProject(project)">
                <template #header>
                  <div class="card-header">
                    <span>{{ project.name }}</span>
                    <el-tag size="small">{{ formatDate(project.created_at) }}</el-tag>
                  </div>
                </template>
                <div class="card-content">
                  <p class="description">{{ project.description || '暂无描述' }}</p>
                  <p class="path">{{ project.workspace_path }}</p>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </div>
      </el-main>
    </el-container>

    <!-- 创建项目对话框 -->
    <el-dialog v-model="showCreateDialog" title="新建项目" width="500px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="项目名称">
          <el-input v-model="createForm.name" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input v-model="createForm.description" type="textarea" placeholder="请输入项目描述（可选）" />
        </el-form-item>
        <el-form-item label="工作区">
          <el-input v-model="createForm.workspace_path" placeholder="已有目录路径（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createProject" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '@/stores'
import { projectApi } from '@/api'
import type { Project } from '@/types'
import dayjs from 'dayjs'

const router = useRouter()
const store = useAgentStore()

const showCreateDialog = ref(false)
const creating = ref(false)
const createForm = ref({
  name: '',
  description: '',
  workspace_path: '' as string | undefined,
})

const projects = computed(() => store.projects)
const hasProjects = computed(() => store.hasProjects)

function formatDate(date: string) {
  return dayjs(date).format('YYYY-MM-DD HH:mm')
}

async function loadProjects() {
  try {
    const data = await projectApi.getProjects()
    store.setProjects(data)
  } catch (error) {
    ElMessage.error('加载项目列表失败')
  }
}

async function createProject() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入项目名称')
    return
  }
  
  creating.value = true
  try {
    const data = await projectApi.createProject({
      name: createForm.value.name,
      description: createForm.value.description,
      workspace_path: createForm.value.workspace_path || null,
    })
    store.setProjects([...store.projects, data])
    ElMessage.success('项目创建成功')
    showCreateDialog.value = false
    createForm.value = { name: '', description: '', workspace_path: '' }
  } catch (error) {
    ElMessage.error('创建项目失败')
  } finally {
    creating.value = false
  }
}

function goToProject(project: Project) {
  store.setCurrentProject(project)
  router.push(`/project/${project.id}`)
}

onMounted(() => {
  loadProjects()
})
</script>

<style scoped lang="scss">
.home {
  height: 100%;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
  border-bottom: 1px solid #e4e7ed;
  
  .logo {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 20px;
    font-weight: bold;
    color: #409eff;
  }
}

.main {
  background-color: #f5f7fa;
  min-height: calc(100vh - 60px);
}

.projects-container {
  max-width: 1200px;
  margin: 0 auto;
  
  h2 {
    margin-bottom: 20px;
    color: #303133;
  }
}

.project-card {
  cursor: pointer;
  margin-bottom: 20px;
  
  &:hover {
    border-color: #409eff;
  }
  
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .card-content {
    .description {
      color: #606266;
      margin-bottom: 10px;
      min-height: 40px;
    }
    
    .path {
      color: #909399;
      font-size: 12px;
      word-break: break-all;
    }
  }
}
</style>