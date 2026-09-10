<template>
  <div class="min-h-full">
    <!-- 主视觉区：点状网格背景 + 创作输入框 -->
    <section class="dot-grid px-6 pt-10 pb-8">
      <div class="max-w-4xl mx-auto">
        <h1 class="text-center text-2xl md:text-3xl font-semibold text-white mb-8 leading-snug">
          短剧漫剧 / 输入你的灵感，<span class="text-gradient-brand">AI 会为你自动策划内容生成视频</span>
        </h1>

        <!-- 创作输入卡片 -->
        <div class="seko-card p-4 md:p-5">
          <!-- 模式 Tab：短片工作室 | 创作Agent·无限画布 -->
          <div class="flex items-center gap-1 mb-3">
            <button
              v-for="t in modeTabs"
              :key="t.key"
              class="px-3 py-1.5 rounded-lg text-sm flex items-center gap-1.5 transition-colors"
              :class="mode === t.key ? 'bg-ink-750 text-white' : 'text-slate-400 hover:text-white'"
              @click="mode = t.key"
            >
              <el-icon :size="15"><component :is="t.icon" /></el-icon>
              {{ t.label }}
            </button>
          </div>

          <!-- 灵感输入 -->
          <el-input
            v-model="prompt"
            type="textarea"
            :rows="3"
            resize="none"
            placeholder="输入你的灵感，AI 会为你自动策划内容生成视频"
            class="explore-input"
            @keydown.enter.exact.prevent="handleCreate"
          />
          <!-- 智能判定提示 -->
          <div class="flex items-center justify-between mt-1.5 text-[11px]" :class="isFullScript ? 'text-brand-400' : 'text-slate-500'">
            <span>{{ hintText }}</span>
            <span v-if="prompt.trim().length > 0">{{ prompt.trim().length }} 字</span>
          </div>

          <!-- 底部操作行 -->
          <div class="flex items-center justify-between mt-3">
            <div class="flex items-center gap-2">
              <!-- 上传剧本 -->
              <el-upload
                :show-file-list="false"
                accept=".txt,.md,.docx"
                :before-upload="handleScriptUpload"
              >
                <button class="seko-btn-ghost !rounded-full !py-1.5 text-sm">
                  <el-icon :size="15"><UploadFilled /></el-icon>
                  上传剧本
                </button>
              </el-upload>
              <!-- 模型选择 -->
              <el-popover placement="top-start" :width="320" trigger="click">
                <template #reference>
                  <button class="seko-btn-ghost !rounded-full !py-1.5 text-sm">
                    <el-icon :size="15"><Cpu /></el-icon>
                    {{ selectedModelLabel }}
                    <el-icon :size="12"><ArrowDown /></el-icon>
                  </button>
                </template>
                <div class="space-y-1 max-h-72 overflow-y-auto">
                  <div
                    v-for="m in videoModels"
                    :key="m.code"
                    class="px-3 py-2 rounded-lg cursor-pointer hover:bg-ink-750 transition"
                    :class="modelId === m.code && 'bg-ink-750'"
                    @click="modelId = m.code"
                  >
                    <div class="text-sm text-slate-100 flex items-center gap-2">
                      {{ m.name }}
                      <span v-if="m.is_recommended" class="seko-tag">推荐</span>
                    </div>
                    <div v-if="m.description" class="text-xs text-slate-500 mt-0.5 line-clamp-1">{{ m.description }}</div>
                  </div>
                </div>
              </el-popover>
            </div>

            <button class="seko-btn-primary !px-6" :disabled="creating" @click="handleCreate">
              <el-icon v-if="creating" class="animate-spin"><Loading /></el-icon>
              <el-icon v-else :size="16"><VideoPlay /></el-icon>
              {{ creating ? 'AI 策划中...' : '开始创作' }}
            </button>
          </div>
        </div>

        <!-- 类型 chips -->
        <div class="flex flex-wrap items-center justify-center gap-3 mt-6">
          <div v-for="c in categories" :key="c.label" class="seko-chip" @click="applyTemplate(c)">
            <span class="text-brand-400">{{ c.emoji }}</span>
            {{ c.label }}
          </div>
        </div>
      </div>
    </section>

    <!-- 特色功能 -->
    <section class="px-6 py-8 max-w-6xl mx-auto">
      <h2 class="seko-section-title">特色功能</h2>
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <div
          v-for="f in features"
          :key="f.title"
          class="seko-card seko-card-hover p-4 cursor-pointer group"
          @click="onFeatureClick(f)"
        >
          <div class="aspect-video rounded-lg mb-3 overflow-hidden bg-ink-800 flex items-center justify-center relative">
            <img v-if="f.cover" :src="f.cover" class="w-full h-full object-cover" />
            <el-icon v-else :size="32" class="text-brand-400"><component :is="f.icon" /></el-icon>
            <span v-if="f.badge" class="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded bg-brand-400 text-black text-[10px] font-semibold">
              {{ f.badge }}
            </span>
          </div>
          <div class="text-sm font-medium text-slate-100 group-hover:text-brand-300 transition line-clamp-1">{{ f.title }}</div>
          <div class="text-xs text-slate-500 mt-1 line-clamp-2">{{ f.desc }}</div>
        </div>
      </div>
    </section>

    <!-- Seko TV / 技能社区 / 资源活动 -->
    <section class="px-6 pb-16 max-w-6xl mx-auto">
      <div class="flex items-center gap-2 mb-5 border-b border-ink-800">
        <button
          v-for="t in contentTabs"
          :key="t"
          class="px-4 py-2.5 text-sm transition-colors relative"
          :class="contentTab === t ? 'text-white font-medium' : 'text-slate-500 hover:text-slate-300'"
          @click="contentTab = t"
        >
          {{ t }}
          <span v-if="contentTab === t" class="absolute left-4 right-4 -bottom-px h-0.5 bg-brand-400 rounded-full" />
        </button>
      </div>

      <!-- 分类筛选 -->
      <div v-if="contentTab === 'Seko TV'" class="flex flex-wrap items-center gap-2 mb-5">
        <button
          v-for="cat in tvCategories"
          :key="cat"
          class="px-3 py-1.5 rounded-full text-xs transition-colors"
          :class="tvCategory === cat ? 'bg-white text-black font-medium' : 'bg-ink-800 text-slate-400 hover:text-white'"
          @click="tvCategory = cat"
        >
          {{ cat }}
        </button>
      </div>

      <!-- 作品网格 -->
      <div v-if="contentTab === 'Seko TV'" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        <div
          v-for="w in filteredWorks"
          :key="w.id"
          class="seko-card seko-card-hover overflow-hidden cursor-pointer group"
          @click="forkWork(w)"
        >
          <div class="aspect-video bg-ink-800 relative overflow-hidden">
            <img v-if="w.cover_url" :src="w.cover_url" class="w-full h-full object-cover group-hover:scale-105 transition duration-500" />
            <div v-else class="w-full h-full flex items-center justify-center">
              <el-icon :size="28" class="text-slate-600"><VideoCamera /></el-icon>
            </div>
            <span class="absolute top-2 left-2 px-1.5 py-0.5 rounded bg-black/60 backdrop-blur text-[10px] text-brand-300 border border-brand-500/30">
              画布
            </span>
          </div>
          <div class="p-3">
            <div class="text-sm text-slate-100 line-clamp-1">{{ w.title }}</div>
            <div class="flex items-center justify-between mt-2 text-xs text-slate-500">
              <span class="flex items-center gap-1"><el-icon :size="12"><User /></el-icon>{{ w.author || 'Seko 用户' }}</span>
              <span class="flex items-center gap-2">
                <span class="flex items-center gap-0.5"><el-icon :size="12"><Star /></el-icon>{{ w.like_count }}</span>
                <span class="flex items-center gap-0.5"><el-icon :size="12"><View /></el-icon>{{ w.view_count }}</span>
              </span>
            </div>
          </div>
        </div>
        <div v-if="!filteredWorks.length" class="col-span-full py-16 text-center text-slate-600 text-sm">
          暂无作品，去创作第一个吧
        </div>
      </div>

      <!-- 技能社区 Tab -->
      <div v-else-if="contentTab === '技能社区'" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        <div
          v-for="s in skills"
          :key="s.id"
          class="seko-card seko-card-hover p-4 cursor-pointer"
          @click="$router.push('/skills')"
        >
          <div class="flex items-center gap-2 mb-2">
            <div class="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/30 flex items-center justify-center text-brand-400 text-sm font-bold">
              {{ s.name.slice(0, 1) }}
            </div>
            <div class="text-sm font-medium text-slate-100">{{ s.name }}</div>
          </div>
          <div class="text-xs text-slate-500 line-clamp-2">{{ s.description }}</div>
          <div class="flex items-center justify-between mt-3 text-xs">
            <span class="text-slate-500">安装 {{ s.install_count }}</span>
            <span v-if="s.is_official" class="seko-tag">官方</span>
          </div>
        </div>
      </div>

      <!-- 资源活动 Tab -->
      <div v-else class="py-16 text-center text-slate-600 text-sm">
        资源活动即将上线，敬请期待
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Film, Connection, UploadFilled, Cpu, ArrowDown, Loading, VideoPlay,
  VideoCamera, User, Star, View, MagicStick, Picture, Headset, Promotion, Brush,
} from '@element-plus/icons-vue'
import { projectsApi, skillsApi, inspirationApi, modelsApi } from '@/api'
import type { Inspiration, Skill, ModelCatalog } from '@/api/types'

const router = useRouter()

// ============ 创作输入 ============
const prompt = ref('')
const mode = ref<'studio' | 'canvas'>('studio')
const creating = ref(false)
const modelId = ref('')

const modeTabs = [
  { key: 'studio', label: '短片工作室', icon: Film },
  { key: 'canvas', label: '创作Agent·无限画布', icon: Connection },
]

// 视频模型
const videoModels = ref<ModelCatalog[]>([])
const selectedModelLabel = computed(() => {
  const m = videoModels.value.find((x) => x.code === modelId.value)
  return m ? m.name : '选择模型'
})

// 类型模板
const categories = [
  { label: '出海短剧', emoji: '🌊', prompt: '写一个出海复仇短剧：女主被豪门未婚夫背叛，重生后逆袭复仇，节奏快、反转多。' },
  { label: '短剧漫剧', emoji: '🎬', prompt: '写一个都市甜宠漫剧：社恐漫画家与高冷总裁的错位恋爱，轻松搞笑。' },
  { label: '知识分享', emoji: '📚', prompt: '做一个 60 秒知识分享短片：3 个提高记忆力的科学方法，口播 + 画面演示。' },
  { label: '音乐MV', emoji: '🎵', prompt: '为一首治愈系民谣生成音乐 MV：海边小镇的夏天告别故事，画面唯美。' },
]

const applyTemplate = (c: { label: string; prompt: string }) => {
  prompt.value = c.prompt
}

// 上传剧本
const handleScriptUpload = (file: File) => {
  const reader = new FileReader()
  reader.onload = () => {
    prompt.value = String(reader.result || '')
    ElMessage.success('剧本已导入，可直接开始创作')
  }
  reader.readAsText(file)
  return false
}

// 开始创作：根据输入长度智能分流
// - 短输入（≤200 字）：当作灵感，走 7 步自动创作
// - 长输入（>200 字）：当作完整剧本，先创建项目 → parse-script 落库为持久化剧本版本 → 再 7 步生成角色/场景/分镜
// 这样避免了原「用 query 传长剧本」的 431 报错。
const isFullScript = computed(() => prompt.value.trim().length > 200)

// 判定提示
const hintText = computed(() => {
  const len = prompt.value.trim().length
  if (len === 0) return '输入你的灵感，AI 会为你自动策划内容生成视频'
  if (len <= 200) return `检测为「灵感描述」（${len} 字）→ 将走 AI 自动策划`
  return `检测为「完整剧本」（${len} 字）→ 将落库为项目剧本并自动拆分角色/场景/分镜`
})

const handleCreate = async () => {
  if (!prompt.value.trim()) {
    ElMessage.warning('请先输入你的灵感或剧本')
    return
  }
  creating.value = true
  try {
    if (isFullScript.value) {
      // ============ 完整剧本路径 ============
      // 1) 创建空项目（只带名字 + prompt）
      const projectName = prompt.value.trim().slice(0, 24) || '未命名项目'
      const project = await projectsApi.create({
        name: projectName,
        prompt: prompt.value,
      })
      ElMessage.info('正在解析完整剧本…')
      // 2) 用 body POST 解析完整剧本（修复 431）
      const parseRes = await projectsApi.parseScript(project.id, {
        script_text: prompt.value,
        format_hint: 'auto',
      })
      if (!parseRes?.ok) {
        ElMessage.error(parseRes?.error || '剧本解析失败')
        return
      }
      ElMessage.success(
        `剧本已保存，已识别 ${parseRes.character_count || 0} 个角色 / ${parseRes.scene_count || 0} 个场景 / ${parseRes.shot_count || 0} 个分镜`,
      )
      router.push(`/canvas/${project.id}`)
    } else {
      // ============ 灵感短描述路径（原 7 步流程） ============
      const project = await projectsApi.create({
        name: prompt.value.slice(0, 24) || '未命名项目',
        prompt: prompt.value,
      })
      ElMessage.info('AI 正在为你自动策划内容...')
      await projectsApi.startCreation(project.id, { prompt: prompt.value })
      router.push(`/canvas/${project.id}`)
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '创作失败，请重试')
  } finally {
    creating.value = false
  }
}

// ============ 特色功能 ============
const features = [
  { title: '空白画布', desc: '从零开始的自由创作空间，节点式组合素材', icon: Picture, action: 'blank-canvas' },
  { title: 'Seedance2.5 视频生成', desc: '最新视频模型，多镜头叙事更连贯', icon: VideoPlay, badge: 'NEW', action: 'seedance' },
  { title: '第一视角催泪短片', desc: '编导李让 · 第一视角情感短片模板', icon: Film, action: 'template-tear' },
  { title: '山音编剧大师2.0', desc: 'Seko 独家 · 专业级剧本创作引擎', icon: MagicStick, badge: '独家', action: 'script-master' },
  { title: '出海剧转绘', desc: '中文剧本一键转制多语言出海短剧', icon: Promotion, action: 'translate' },
]

const onFeatureClick = async (f: { action: string; title: string }) => {
  if (f.action === 'blank-canvas') {
    try {
      const project = await projectsApi.create({ name: '空白画布' })
      router.push(`/canvas/${project.id}`)
    } catch {
      ElMessage.error('创建失败')
    }
    return
  }
  if (f.action === 'seedance') {
    modelId.value = 'seedance-2.0'
    ElMessage.success('已选择 Seedance 2.0 视频模型')
    return
  }
  if (f.action === 'script-master') {
    prompt.value = '请以专业编剧水准创作一部 5 集都市情感短剧大纲，要求人物弧光完整、每集结尾有钩子。'
    return
  }
  if (f.action === 'translate') {
    prompt.value = '把下面的中文短剧剧本转制为英语出海版本，保留节奏与反转：'
    return
  }
  // 第一视角催泪短片模板
  prompt.value = '创作一部第一视角催泪短片：一位父亲在女儿婚礼前夜，翻看她从小到大的照片，回忆涌上心头。'
}

// ============ 内容区 ============
const contentTabs = ['Seko TV', '技能社区', '资源活动']
const contentTab = ref('Seko TV')

const tvCategories = ['全部', '精选画布', '短剧漫剧', '叙事短片', 'IP剧集', '动画二次元', '广告TVC', '教程案例']
const tvCategory = ref('全部')

const works = ref<Inspiration[]>([])
const filteredWorks = computed(() => {
  if (tvCategory.value === '全部') return works.value
  return works.value.filter((w) => w.category === tvCategory.value || tvCategory.value === '精选画布')
})

const skills = ref<Skill[]>([])

const forkWork = async (w: Inspiration) => {
  try {
    await inspirationApi.fork(w.id)
    ElMessage.success('已复刻该作品，正在打开项目')
    router.push('/projects')
  } catch {
    router.push('/projects')
  }
}

onMounted(async () => {
  try {
    const [workRes, skillRes, modelRes] = await Promise.all([
      inspirationApi.list({ limit: 12 }),
      skillsApi.list(),
      modelsApi.list(),
    ])
    works.value = workRes.items
    skills.value = skillRes.slice(0, 8)
    videoModels.value = modelRes.filter((m) => m.model_type === 'video')
    if (videoModels.value.length) {
      const rec = videoModels.value.find((m) => m.is_recommended)
      modelId.value = (rec || videoModels.value[0]).code
    }
  } catch {
    // 静默失败，保留空态
  }
})
</script>

<style scoped>
.explore-input :deep(.el-textarea__inner) {
  background: transparent;
  border: none;
  box-shadow: none;
  color: #ebebeb;
  font-size: 14px;
  padding: 4px 2px;
}
.explore-input :deep(.el-textarea__inner)::placeholder {
  color: #6b6b6b;
}
</style>
