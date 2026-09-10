<template>
  <div class="px-6 py-8 max-w-6xl mx-auto">
    <!-- 标题行 -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="seko-section-title !mb-0">我的项目</h1>
      <button class="seko-btn-primary" @click="createBlank">
        <el-icon :size="15"><Plus /></el-icon>
        新建画布
      </button>
    </div>

    <!-- 项目网格 -->
    <div v-if="projects.length" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      <div
        v-for="p in projects"
        :key="p.id"
        class="seko-card seko-card-hover overflow-hidden cursor-pointer group"
        @click="$router.push(`/canvas/${p.id}`)"
      >
        <div class="aspect-video bg-ink-800 relative overflow-hidden">
          <img v-if="p.cover_url" :src="p.cover_url" class="w-full h-full object-cover group-hover:scale-105 transition duration-500" />
          <div v-else class="w-full h-full dot-grid flex items-center justify-center">
            <el-icon :size="30" class="text-slate-600"><Film /></el-icon>
          </div>
          <!-- 状态徽标 -->
          <span
            class="absolute top-2 left-2 px-1.5 py-0.5 rounded text-[10px] font-medium"
            :class="statusClass(p.status)"
          >
            {{ statusText(p.status) }}
          </span>
          <!-- 悬浮操作 -->
          <div class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition flex items-center justify-center gap-2">
            <button class="seko-btn-primary !py-1.5 !px-4 text-xs" @click.stop="$router.push(`/canvas/${p.id}`)">
              进入画布
            </button>
            <button class="seko-btn-dark !py-1.5 !px-3 text-xs border border-ink-600" @click.stop="removeProject(p)">
              <el-icon :size="13"><Delete /></el-icon>
            </button>
          </div>
        </div>
        <div class="p-3">
          <div class="text-sm text-slate-100 line-clamp-1">{{ p.name }}</div>
          <div class="flex items-center justify-between mt-2 text-xs text-slate-500">
            <span>{{ p.episode_count }} 集 · {{ p.shot_count }} 分镜</span>
            <span v-if="p.task_pending > 0" class="text-brand-400 flex items-center gap-1">
              <el-icon class="animate-spin" :size="11"><Loading /></el-icon>
              生成中 {{ p.task_pending }}
            </span>
            <span v-else>{{ formatDate(p.updated_at) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 空态 -->
    <div v-else class="py-24 text-center">
      <el-icon :size="48" class="text-slate-700"><FolderOpened /></el-icon>
      <div class="text-slate-500 text-sm mt-4">还没有项目，去首页输入灵感开始创作吧</div>
      <button class="seko-btn-primary mt-6" @click="$router.push('/explore')">开始创作</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Film, Delete, Loading, FolderOpened } from '@element-plus/icons-vue'
import { projectsApi } from '@/api'
import type { Project } from '@/api/types'

const router = useRouter()
const projects = ref<Project[]>([])

const load = async () => {
  try {
    const res = await projectsApi.list({ limit: 50 })
    projects.value = res.items
  } catch {
    /* ignore */
  }
}

const createBlank = async () => {
  try {
    const p = await projectsApi.create({ name: `未命名项目 ${new Date().toLocaleDateString()}` })
    router.push(`/canvas/${p.id}`)
  } catch {
    ElMessage.error('创建失败')
  }
}

const removeProject = async (p: Project) => {
  try {
    await ElMessageBox.confirm(`确定删除项目「${p.name}」？`, '删除项目', { type: 'warning' })
    await projectsApi.remove(p.id)
    ElMessage.success('已删除')
    load()
  } catch {
    /* 取消 */
  }
}

const statusText = (s: string) =>
  ({ draft: '草稿', running: '生成中', completed: '已完成', failed: '失败' }[s] || s)

const statusClass = (s: string) =>
  ({
    draft: 'bg-ink-700 text-slate-300',
    running: 'bg-brand-500/20 text-brand-300 border border-brand-500/40',
    completed: 'bg-emerald-500/20 text-emerald-300',
    failed: 'bg-red-500/20 text-red-300',
  }[s] || 'bg-ink-700 text-slate-300')

const formatDate = (iso: string) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

onMounted(load)
</script>
