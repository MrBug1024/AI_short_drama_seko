<template>
  <div class="px-6 py-8 max-w-6xl mx-auto">
    <!-- 标题行 -->
    <div class="flex items-center justify-between mb-6">
      <h1 class="lbp-section-title !mb-0">我的项目</h1>
      <button class="lbp-btn-primary" @click="openCreateDialog">
        <el-icon :size="15"><Plus /></el-icon>
        开始创作
      </button>
    </div>

    <!-- 项目网格 -->
    <div v-if="projects.length" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      <div
        v-for="p in projects"
        :key="p.id"
        class="lbp-card lbp-card-hover overflow-hidden cursor-pointer group"
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
            <button class="lbp-btn-primary !py-1.5 !px-4 text-xs" @click.stop="$router.push(`/canvas/${p.id}`)">
              进入画布
            </button>
            <button class="lbp-btn-dark !py-1.5 !px-3 text-xs border border-ink-600" @click.stop="removeProject(p)">
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
      <div class="text-slate-500 text-sm mt-4">还没有项目，点击下方按钮从剧本开始创作</div>
      <button class="lbp-btn-primary mt-6" @click="openCreateDialog">开始创作</button>
    </div>

    <!-- ============ 开始创作对话框：剧名 + 剧本 → 一步创建项目+落库+AI 解析 ============ -->
    <el-dialog
      v-model="createDialog.visible"
      title="开始创作 · 填写剧本"
      width="640px"
      append-to-body
      destroy-on-close
    >
      <div class="space-y-3">
        <div>
          <div class="text-xs text-slate-400 mb-1.5">剧名 <span class="text-red-400">*</span></div>
          <el-input
            v-model="createDialog.name"
            placeholder="给你的短剧起个名字，如《出海复仇记》"
            maxlength="80"
            show-word-limit
          />
        </div>
        <div>
          <div class="text-xs text-slate-400 mb-1.5">完整剧本 <span class="text-red-400">*</span></div>
          <el-input
            v-model="createDialog.scriptText"
            type="textarea"
            :rows="8"
            placeholder="粘贴或输入完整剧本（剧情剧本 / 旁白解说 / 分镜表均可）。AI 会自动识别角色、场景、分镜并把它们落到无限画布上。"
            resize="vertical"
          />
          <div class="flex items-center justify-between mt-1 text-[11px] text-slate-500">
            <span>{{ createDialog.scriptText.trim().length }} 字</span>
            <el-upload
              :show-file-list="false"
              accept=".txt,.md,.docx"
              :before-upload="handleUpload"
            >
              <button class="text-brand-400 hover:underline">上传剧本文件</button>
            </el-upload>
          </div>
        </div>
        <div class="text-[11px] text-slate-500 bg-ink-850 rounded-lg px-3 py-2 border border-ink-800">
          <p class="mb-1 text-slate-400">创作流程：</p>
          <ol class="list-decimal list-inside space-y-0.5">
            <li>创建项目并落库剧本 v1</li>
            <li>AI 解析出角色 / 场景 / 分镜</li>
            <li>自动建立无限画布节点</li>
            <li>进入画布后可逐节点生成图像 / 视频 / 调整效果</li>
          </ol>
        </div>
      </div>
      <template #footer>
        <button class="lbp-btn-ghost !py-1.5 text-xs" @click="createDialog.visible = false">取消</button>
        <button
          class="lbp-btn-primary !py-1.5 text-xs"
          :disabled="!canCreate || creating"
          @click="confirmCreate"
        >
          <el-icon v-if="creating" class="animate-spin" :size="13"><Loading /></el-icon>
          <el-icon v-else :size="13"><VideoPlay /></el-icon>
          {{ creating ? '创建中...' : '开始创作' }}
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Film, Delete, Loading, FolderOpened, VideoPlay } from '@element-plus/icons-vue'
import { projectsApi } from '@/api'
import type { Project } from '@/api/types'

const router = useRouter()
const projects = ref<Project[]>([])

// ============ 开始创作对话框 ============
const createDialog = ref({
  visible: false,
  name: '',
  scriptText: '',
})
const creating = ref(false)

const canCreate = computed(
  () => createDialog.value.name.trim().length > 0 && createDialog.value.scriptText.trim().length >= 10,
)

const openCreateDialog = () => {
  createDialog.value.visible = true
  createDialog.value.name = ''
  createDialog.value.scriptText = ''
}

const handleUpload = (file: File) => {
  const reader = new FileReader()
  reader.onload = () => {
    createDialog.value.scriptText = String(reader.result || '')
    ElMessage.success('剧本已导入')
  }
  reader.readAsText(file)
  return false
}

const confirmCreate = async () => {
  if (!canCreate.value) {
    ElMessage.warning('请填写剧名 + 至少 10 字剧本')
    return
  }
  creating.value = true
  try {
    ElMessage.info('正在创建项目并解析剧本…')
    const res = await projectsApi.createWithScript({
      name: createDialog.value.name.trim(),
      script_text: createDialog.value.scriptText,
      format_hint: 'auto',
    })
    if (!res?.ok) {
      ElMessage.error('创建失败')
      return
    }
    ElMessage.success(
      `已创建项目并落库剧本 v${res.script_version}，识别 ${res.character_count} 角色 / ${res.scene_count} 场景 / ${res.shot_count} 分镜`,
    )
    createDialog.value.visible = false
    router.push(`/canvas/${res.project_id}`)
  } catch (e: any) {
    ElMessage.error(e?.message || '创作失败，请重试')
  } finally {
    creating.value = false
  }
}

const load = async () => {
  try {
    const res = await projectsApi.list({ limit: 50 })
    projects.value = res.items
  } catch {
    /* ignore */
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
