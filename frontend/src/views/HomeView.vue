<template>
  <div class="min-h-full">
    <!-- 主视觉区：点状网格背景 + 创作输入框 -->
    <section class="dot-grid px-6 pt-10 pb-8">
      <div class="max-w-4xl mx-auto">
        <h1 class="text-center text-2xl md:text-3xl font-semibold text-white mb-8 leading-snug">
          短剧漫剧 / 输入你的灵感，<span class="text-gradient-brand">AI 会为你自动策划内容生成视频</span>
        </h1>

        <!-- 创作输入卡片：统一剧本入口（剧名 + 完整剧本 → 一步创建项目+落库+AI 解析画布） -->
        <div class="lbp-card p-4 md:p-5">
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

          <!-- 剧名（必填，单行） -->
          <el-input
            v-model="projectName"
            placeholder="给你的短剧起个名字，如《出海复仇记》"
            class="!mb-2"
            maxlength="80"
            show-word-limit
          />

          <!-- 剧本正文（必填，文本域；后端用 body 提交，规避 431） -->
          <el-input
            v-model="scriptText"
            type="textarea"
            :rows="5"
            resize="none"
            placeholder="粘贴或输入完整剧本（剧情剧本 / 旁白解说 / 分镜表均可）。AI 会自动识别角色、场景、分镜，并把它们落到无限画布上。"
            class="explore-input"
          />
          <!-- 字数 + 状态提示 -->
          <div class="flex items-center justify-between mt-1.5 text-[11px]" :class="scriptText.trim().length >= 10 ? 'text-brand-400' : 'text-slate-500'">
            <span>{{ hintText }}</span>
            <span v-if="scriptText.trim().length > 0">{{ scriptText.trim().length }} 字</span>
          </div>

          <!-- 底部操作行 -->
          <div class="flex items-center justify-between mt-3">
            <div class="flex items-center gap-2">
              <!-- 上传剧本文件 -->
              <el-upload
                :show-file-list="false"
                accept=".txt,.md,.docx"
                :before-upload="handleScriptUpload"
              >
                <button class="lbp-btn-ghost !rounded-full !py-1.5 text-sm">
                  <el-icon :size="15"><UploadFilled /></el-icon>
                  上传剧本文件
                </button>
              </el-upload>
              <!-- 模型选择 -->
              <el-popover placement="top-start" :width="320" trigger="click">
                <template #reference>
                  <button class="lbp-btn-ghost !rounded-full !py-1.5 text-sm">
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
                      <span v-if="m.is_recommended" class="lbp-tag">推荐</span>
                    </div>
                    <div v-if="m.description" class="text-xs text-slate-500 mt-0.5 line-clamp-1">{{ m.description }}</div>
                  </div>
                </div>
              </el-popover>
            </div>

            <button class="lbp-btn-primary !px-6" :disabled="creating || !canSubmit" @click="handleCreate">
              <el-icon v-if="creating" class="animate-spin"><Loading /></el-icon>
              <el-icon v-else :size="16"><VideoPlay /></el-icon>
              {{ creating ? 'AI 策划中...' : '开始创作' }}
            </button>
          </div>
        </div>

        <!-- 类型 chips -->
        <div class="flex flex-wrap items-center justify-center gap-3 mt-6">
          <div v-for="c in categories" :key="c.label" class="lbp-chip" @click="applyTemplate(c)">
            <span class="text-brand-400">{{ c.emoji }}</span>
            {{ c.label }}
          </div>
        </div>
      </div>
    </section>

    <!-- 特色功能 -->
    <section class="px-6 py-8 max-w-6xl mx-auto">
      <h2 class="lbp-section-title">特色功能</h2>
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        <div
          v-for="f in features"
          :key="f.title"
          class="lbp-card lbp-card-hover p-4 cursor-pointer group"
          @click="onFeatureClick(f)"
        >
          <div class="aspect-video rounded-lg mb-3 overflow-hidden bg-ink-800 flex items-center justify-center relative">
            <el-icon :size="32" class="text-brand-400"><component :is="f.icon" /></el-icon>
            <span v-if="f.badge" class="absolute top-1.5 left-1.5 px-1.5 py-0.5 rounded bg-brand-400 text-black text-[10px] font-semibold">
              {{ f.badge }}
            </span>
          </div>
          <div class="text-sm font-medium text-slate-100 group-hover:text-brand-300 transition line-clamp-1">{{ f.title }}</div>
          <div class="text-xs text-slate-500 mt-1 line-clamp-2">{{ f.desc }}</div>
        </div>
      </div>
    </section>

    <!-- LBP_M TV / 技能社区 / 资源活动 -->
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
      <div v-if="contentTab === 'LBP_M TV'" class="flex flex-wrap items-center gap-2 mb-5">
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
      <div v-if="contentTab === 'LBP_M TV'" class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        <div
          v-for="w in filteredWorks"
          :key="w.id"
          class="lbp-card lbp-card-hover overflow-hidden cursor-pointer group"
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
              <span class="flex items-center gap-1"><el-icon :size="12"><User /></el-icon>{{ w.author || 'LBP_M 用户' }}</span>
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
          class="lbp-card lbp-card-hover p-4 cursor-pointer"
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
            <span v-if="s.is_official" class="lbp-tag">官方</span>
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

// ============ 创作输入（剧名 + 完整剧本 → 一步创建项目+落库+AI 解析画布） ============
const projectName = ref('')
const scriptText = ref('')
const mode = ref<string>('studio')
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

// 类型模板：点击直接填到剧本框（这是「AI 剧本扩写」思路：用户选题材 → AI 补一段短剧本；下面留口子）
const categories = [
  { label: '出海短剧', emoji: '🌊', prompt: '写一个出海复仇短剧：女主被豪门未婚夫背叛，重生后逆袭复仇，节奏快、反转多。' },
  { label: '短剧漫剧', emoji: '🎬', prompt: '写一个都市甜宠漫剧：社恐漫画家与高冷总裁的错位恋爱，轻松搞笑。' },
  { label: '知识分享', emoji: '📚', prompt: '做一个 60 秒知识分享短片：3 个提高记忆力的科学方法，口播 + 画面演示。' },
  { label: '音乐MV', emoji: '🎵', prompt: '为一首治愈系民谣生成音乐 MV：海边小镇的夏天告别故事，画面唯美。' },
]

const applyTemplate = (c: { label: string; prompt: string }) => {
  // 模板填充剧本框（注意：这是「题材种子」，用户可继续编辑）
  scriptText.value = c.prompt
  if (!projectName.value) {
    projectName.value = c.label
  }
  ElMessage.info(`已填入「${c.label}」题材种子，请补充为完整剧本或直接点击开始创作`)
}

// 上传剧本文件
const handleScriptUpload = (file: File) => {
  const reader = new FileReader()
  reader.onload = () => {
    scriptText.value = String(reader.result || '')
    ElMessage.success('剧本已导入，请补充剧名后点击开始创作')
  }
  reader.readAsText(file)
  return false
}

// 可提交校验
const canSubmit = computed(
  () => projectName.value.trim().length > 0 && scriptText.value.trim().length >= 10,
)

// 提示文字
const hintText = computed(() => {
  const len = scriptText.value.trim().length
  if (!projectName.value.trim()) return '先给短剧起个名字，再粘贴完整剧本'
  if (len === 0) return '粘贴或上传完整剧本（剧情剧本 / 旁白解说 / 分镜表）'
  if (len < 10) return `剧本至少 10 字（当前 ${len}）`
  return '点击「开始创作」：AI 会识别角色/场景/分镜，并自动建立画布骨架'
})

// 开始创作（统一入口 → POST /projects/create-with-script）
const handleCreate = async () => {
  if (!canSubmit.value) {
    ElMessage.warning('请填写剧名 + 至少 10 字剧本')
    return
  }
  creating.value = true
  try {
    ElMessage.info('正在创建项目并解析剧本…')
    const res = await projectsApi.createWithScript({
      name: projectName.value.trim(),
      script_text: scriptText.value,
      format_hint: 'auto',
    })
    if (!res?.ok) {
      ElMessage.error('创作失败')
      return
    }
    ElMessage.success(
      `已创建项目并落库剧本 v${res.script_version}，识别 ${res.character_count} 个角色 / ${res.scene_count} 个场景 / ${res.shot_count} 个分镜`,
    )
    router.push(`/canvas/${res.project_id}`)
  } catch (e: any) {
    ElMessage.error(e?.message || '创作失败，请重试')
  } finally {
    creating.value = false
  }
}

// ============ 特色功能 ============
const features = [
  { title: 'Seedance2.5 视频生成', desc: '最新视频模型，多镜头叙事更连贯', icon: VideoPlay, badge: 'NEW', action: 'seedance' },
  { title: '第一视角催泪短片', desc: '编导李让 · 第一视角情感短片模板', icon: Film, action: 'template-tear' },
  { title: '山音编剧大师2.0', desc: 'LBP_M 独家 · 专业级剧本创作引擎', icon: MagicStick, badge: '独家', action: 'script-master' },
  { title: '出海剧转绘', desc: '中文剧本一键转制多语言出海短剧', icon: Promotion, action: 'translate' },
]

const onFeatureClick = (f: { action: string; title: string }) => {
  if (f.action === 'seedance') {
    modelId.value = 'seedance-2.0'
    ElMessage.success('已选择 Seedance 2.0 视频模型')
    return
  }
  // 其他模板：把素材填到剧本框，引导用户点「开始创作」
  if (f.action === 'template-tear') {
    projectName.value = '第一视角催泪短片'
    scriptText.value = '创作一部第一视角催泪短片：一位父亲在女儿婚礼前夜，翻看她从小到大的照片，回忆涌上心头。'
    ElMessage.info('已填入模板，请补充剧名/剧本后点击「开始创作」')
    return
  }
  if (f.action === 'script-master') {
    projectName.value = '山音编剧大师 · 都市情感短剧'
    scriptText.value = '请以专业编剧水准创作一部 5 集都市情感短剧大纲，要求人物弧光完整、每集结尾有钩子。'
    ElMessage.info('已填入模板，请点击「开始创作」')
    return
  }
  if (f.action === 'translate') {
    projectName.value = '出海剧转绘'
    scriptText.value = '把下面的中文短剧剧本转制为英语出海版本，保留节奏与反转：\n\n（粘贴你的中文剧本…）'
    ElMessage.info('已填入模板，请补充剧本后点击「开始创作」')
    return
  }
}

// ============ 内容区 ============
const contentTabs = ['LBP_M TV', '技能社区', '资源活动']
const contentTab = ref('LBP_M TV')

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
