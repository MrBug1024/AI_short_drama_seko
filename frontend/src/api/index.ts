import axios, { type AxiosInstance } from 'axios'
import { ElMessage } from 'element-plus'

// token：与 authStore 同步（authStore 也管理 localStorage）
const TOKEN_KEY = 'lbp_m_token'
function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

// 统一 axios 客户端，baseURL 通过 vite proxy 转发到后端 8000
const http: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 300000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截：自动注入 Bearer Token
http.interceptors.request.use((config) => {
  const tk = getToken()
  if (tk) {
    config.headers = config.headers || {}
    ;(config.headers as Record<string, string>)['Authorization'] = `Bearer ${tk}`
  }
  return config
})

// 响应拦截：401 时清空本地 token + 跳登录页（仅在「已登录」时跳转避免无限重定向）
let _isRedirecting401 = false
http.interceptors.response.use(
  (r) => r,
  (err) => {
    const status = err?.response?.status
    const detail = err?.response?.data?.detail
    // 跳过 /auth/* 自身的错误（避免登录失败时跳转登录页造成循环）
    const url: string = err?.config?.url || ''
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/register') || url.includes('/auth/me')

    if (status === 401 && getToken() && !isAuthEndpoint && !_isRedirecting401) {
      // token 失效：清空本地态
      localStorage.removeItem(TOKEN_KEY)
      _isRedirecting401 = true
      ElMessage.warning('登录状态已过期，请重新登录')
      // 用 window.location 强制刷新 router 状态
      setTimeout(() => {
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
        _isRedirecting401 = false
      }, 100)
    } else {
      const msg = typeof detail === 'string' ? detail : (detail?.msg || err?.message || '请求失败')
      ElMessage.error(msg)
    }
    return Promise.reject(err)
  },
)

export default http

// ============================================================
// Projects（项目管理 + 7 步创作流）
// ============================================================
import type {
  Project, Episode, Shot, Character, Scene, Prop,
  CanvasNode, CanvasEdge, CanvasSnapshot, GenerationTask,
  Skill, Inspiration, ModelCatalog, ArtStyle, DashboardStats,
  CharacterRelation,
} from './types'

export const projectsApi = {
  list: (params?: { keyword?: string; status?: string; limit?: number; offset?: number }) =>
    http.get<{ items: Project[]; total: number }>('/projects', { params }).then((r) => r.data),
  get: (id: number) => http.get<Project>(`/projects/${id}`).then((r) => r.data),
  create: (data: {
    name: string
    description?: string
    art_style?: string
    target_episodes?: number
    target_duration_sec?: number
    prompt?: string
    skill_code?: string
  }) => http.post<Project>('/projects', data).then((r) => r.data),
  update: (id: number, data: Partial<Project>) =>
    http.patch<Project>(`/projects/${id}`, data).then((r) => r.data),
  remove: (id: number) => http.delete(`/projects/${id}`).then((r) => r.data),

  // 启动 7 步创作流程（走 JSON body，避免长 prompt 触发 431）
  startCreation: (id: number, params: { prompt?: string; art_style?: string; skill_code?: string }) =>
    http.post<{ ok: boolean }>(`/projects/${id}/create`, params || {}).then((r) => r.data),
  // 单步优化
  refine: (id: number, params: { step: string; user_prompt: string; target_type?: string; target_id?: number }) =>
    http.post<{ ok: boolean }>(`/projects/${id}/refine`, null, { params }).then((r) => r.data),

  // 剧集
  listEpisodes: (id: number) => http.get<Episode[]>(`/projects/${id}/episodes`).then((r) => r.data),
  createEpisode: (id: number, data: { title?: string; synopsis?: string }) =>
    http.post<Episode>(`/projects/${id}/episodes`, data).then((r) => r.data),

  // 剧本解析 / 多剧集拆分 / 批量生成
  parseScript: (id: number, params: { script_text: string; format_hint?: string }) =>
    http.post<{ ok: boolean; shots_created?: number; script_id?: number; script_version?: number }>(`/projects/${id}/parse-script`, params).then((r) => r.data),
  /**
   * 一步式创建项目 + 剧本 + AI 解析（角色/场景/分镜 + 画布骨架）
   * 这是「开始创作」按钮的统一入口。body 体提交，规避 431 错误。
   */
  createWithScript: (data: {
    name: string
    script_text: string
    description?: string
    art_style?: string
    format_hint?: string
    skill_code?: string
  }) =>
    http.post<{
      ok: boolean
      project_id: number
      script_id: number
      script_version: number
      shot_count: number
      character_count: number
      scene_count: number
      canvas_node_count: number
      task_id: number
    }>('/projects/create-with-script', data).then((r) => r.data),
  multiEpisodeSplit: (id: number, params: { total_episodes?: number }) =>
    http.post<{ ok: boolean }>(`/projects/${id}/multi-episode-split`, null, { params }).then((r) => r.data),
  batchImages: (id: number, params?: { shot_ids?: number[]; image_model?: string }) =>
    http.post<{ ok: boolean; count?: number }>(`/projects/${id}/batch-generate-shot-images`, null, { params }).then((r) => r.data),
  batchVideos: (id: number, params?: { shot_ids?: number[]; video_model?: string }) =>
    http.post<{ ok: boolean; count?: number }>(`/projects/${id}/batch-generate-shot-videos`, null, { params }).then((r) => r.data),
  compose: (id: number, params?: { shot_ids?: number[]; bgm_url?: string; add_subtitle?: boolean; transition?: string }) =>
    http.post<{ ok: boolean; video_url?: string }>(`/projects/${id}/compose`, null, { params }).then((r) => r.data),
}

export const episodesApi = {
  update: (id: number, data: { title?: string; synopsis?: string; status?: string }) =>
    http.patch<Episode>(`/episodes/${id}`, data).then((r) => r.data),
  remove: (id: number) => http.delete(`/episodes/${id}`).then((r) => r.data),
}

// ============================================================
// 资产（角色/场景/道具/分镜）
// ============================================================
export const assetsApi = {
  characters: (projectId: number) => http.get<Character[]>(`/projects/${projectId}/characters`).then((r) => r.data),
  scenes: (projectId: number) => http.get<Scene[]>(`/projects/${projectId}/scenes`).then((r) => r.data),
  props: (projectId: number) => http.get<Prop[]>(`/projects/${projectId}/props`).then((r) => r.data),
  shots: (projectId: number) => http.get<Shot[]>(`/projects/${projectId}/shots`).then((r) => r.data),

  createCharacter: (projectId: number, data: Partial<Character>) =>
    http.post<Character>(`/projects/${projectId}/characters`, data).then((r) => r.data),
  createScene: (projectId: number, data: Partial<Scene>) =>
    http.post<Scene>(`/projects/${projectId}/scenes`, data).then((r) => r.data),
  createShot: (projectId: number, data: Partial<Shot>) =>
    http.post<Shot>(`/projects/${projectId}/shots`, data).then((r) => r.data),

  updateShot: (id: number, data: Partial<Shot>) => http.patch<Shot>(`/shots/${id}`, data).then((r) => r.data),
  updateCharacter: (id: number, data: Partial<Character>) => http.patch<Character>(`/characters/${id}`, data).then((r) => r.data),
  updateScene: (id: number, data: Partial<Scene>) => http.patch<Scene>(`/scenes/${id}`, data).then((r) => r.data),
}

// ============================================================
// 无限画布
// ============================================================
export const canvasApi = {
  // 全量快照 {nodes, edges}
  snapshot: (projectId: number) =>
    http.get<CanvasSnapshot>(`/projects/${projectId}/canvas`).then((r) => r.data),
  createNode: (projectId: number, data: {
    node_type: string
    ref_id?: number
    title?: string
    position_x?: number
    position_y?: number
    thumbnail_url?: string
    meta?: Record<string, any>
  }) => http.post<CanvasNode>(`/projects/${projectId}/canvas/nodes`, data).then((r) => r.data),
  updateNode: (nid: number, data: {
    title?: string
    position_x?: number
    position_y?: number
    thumbnail_url?: string
    status?: string
    meta?: Record<string, any>
  }) => http.patch<CanvasNode>(`/canvas/nodes/${nid}`, data).then((r) => r.data),
  deleteNode: (nid: number) => http.delete(`/canvas/nodes/${nid}`).then((r) => r.data),
  createEdge: (projectId: number, data: { source_id: number; target_id: number; edge_type?: string; label?: string }) =>
    http.post<CanvasEdge>(`/projects/${projectId}/canvas/edges`, data).then((r) => r.data),
  deleteEdge: (eid: number) => http.delete(`/canvas/edges/${eid}`).then((r) => r.data),
}

// ============================================================
// 生成任务
// ============================================================
export const tasksApi = {
  list: (params?: { project_id?: number; status?: string; task_type?: string; limit?: number }) =>
    http.get<GenerationTask[]>('/generation/tasks', { params }).then((r) => r.data),
  get: (id: number) => http.get<GenerationTask>(`/generation/tasks/${id}`).then((r) => r.data),
  cancel: (id: number) => http.post<GenerationTask>(`/generation/tasks/${id}/cancel`).then((r) => r.data),
  remove: (id: number) => http.delete(`/generation/tasks/${id}`).then((r) => r.data),

  // 项目级生成（后端参数为 query）
  generateImage: (projectId: number, params: {
    prompt: string
    negative_prompt?: string
    shot_id?: number
    character_id?: number
    scene_id?: number
    prop_id?: number
  }) => http.post<GenerationTask>(`/projects/${projectId}/generation/image`, null, { params }).then((r) => r.data),
  generateVideo: (projectId: number, params: {
    prompt: string
    image_url?: string
    duration?: number
    shot_id?: number
  }) => http.post<GenerationTask>(`/projects/${projectId}/generation/video`, null, { params }).then((r) => r.data),
  audioSeparate: (projectId: number, params: { video_url: string }) =>
    http.post<GenerationTask>(`/projects/${projectId}/generation/audio-separate`, null, { params }).then((r) => r.data),
  lipsync: (projectId: number, params: { video_url: string; audio_url: string; shot_id?: number; characters?: string }) =>
    http.post<GenerationTask>(`/projects/${projectId}/generation/lipsync`, null, { params }).then((r) => r.data),
}

// ============================================================
// 剧本资源管理（剧本是一等公民，不再是临时资产）
// ============================================================
export interface ScriptVersion {
  id: number
  project_id: number
  version: number
  title: string
  logline: string
  content: string
  raw_text: string
  meta: Record<string, any>
  source_task_id: string
  created_at: string
  updated_at: string
}

export const scriptsApi = {
  /** 列出版本列表（按版本倒序），返回 {items, total, current_version} */
  list: (projectId: number) =>
    http.get<{ items: ScriptVersion[]; total: number; current_version: number }>(`/projects/${projectId}/scripts`).then((r) => r.data),
  /** 读取单个版本的完整剧本（含 meta） */
  get: (scriptId: number) => http.get<ScriptVersion>(`/scripts/${scriptId}`).then((r) => r.data),
  /** 编辑剧本（标题/梗概/完整内容），不改 meta */
  update: (scriptId: number, data: { title?: string; logline?: string; content?: string }) =>
    http.patch<{ ok: boolean; script_id: number; version: number }>(`/scripts/${scriptId}`, data).then((r) => r.data),
  /** 把指定剧本版本重新应用到画布（重新解析角色/场景/分镜/画布节点） */
  applyToCanvas: (scriptId: number) =>
    http.post<{ ok: boolean; shot_count: number; character_count: number; scene_count: number; canvas_node_count: number }>(`/scripts/${scriptId}/apply-to-canvas`).then((r) => r.data),
}

// ============================================================
// 设计工作台（角色设计稿 / AI 优化 / 角色关系）
// ============================================================
export const designApi = {
  // 角色多视图设计稿（views: closeup,front,side,back,expression）
  designSheet: (characterId: number, views = 'closeup,front,side,expression') =>
    http.post(`/characters/${characterId}/design-sheet`, null, { params: { views } }).then((r) => r.data),
  // 单视图重roll
  generateView: (characterId: number, view: string, extraPrompt = '') =>
    http.post(`/characters/${characterId}/generate-view`, null, { params: { view, extra_prompt: extraPrompt } }).then((r) => r.data),
  // AI 优化角色设定
  optimizeCharacter: (characterId: number, requirement: string) =>
    http.post(`/characters/${characterId}/optimize`, null, { params: { requirement } }).then((r) => r.data),
  // AI 优化场景设定
  optimizeScene: (sceneId: number, requirement: string) =>
    http.post(`/scenes/${sceneId}/optimize`, null, { params: { requirement } }).then((r) => r.data),
  // 生成/重roll 场景图
  generateSceneImage: (sceneId: number, extraPrompt = '') =>
    http.post(`/scenes/${sceneId}/generate-image`, null, { params: { extra_prompt: extraPrompt } }).then((r) => r.data),
  // AI 优化分镜
  optimizeShot: (shotId: number, requirement: string) =>
    http.post(`/shots/${shotId}/optimize`, null, { params: { requirement } }).then((r) => r.data),
  // 生成/重roll 分镜图（专业 prompt）
  generateShotImage: (shotId: number, extraPrompt = '') =>
    http.post(`/shots/${shotId}/generate-image`, null, { params: { extra_prompt: extraPrompt } }).then((r) => r.data),
  // AI 优化整部剧本（生成新版本并同步实体）
  optimizeScript: (projectId: number, requirement: string) =>
    http.post(`/projects/${projectId}/optimize-script`, null, { params: { requirement } }).then((r) => r.data),
  // 角色关系
  listRelations: (projectId: number) =>
    http.get<CharacterRelation[]>(`/projects/${projectId}/relations`).then((r) => r.data),
  createRelation: (projectId: number, data: { from_character_id: number; to_character_id: number; relation_type: string; description?: string }) =>
    http.post<CharacterRelation>(`/projects/${projectId}/relations`, data).then((r) => r.data),
  updateRelation: (relationId: number, data: Partial<{ relation_type: string; description: string }>) =>
    http.patch<CharacterRelation>(`/relations/${relationId}`, data).then((r) => r.data),
  deleteRelation: (relationId: number) =>
    http.delete(`/relations/${relationId}`).then((r) => r.data),
  autoGenerateRelations: (projectId: number) =>
    http.post(`/projects/${projectId}/relations/auto-generate`).then((r) => r.data),

  // AI 补充空白字段（不重写已有内容）
  enrichCharacter: (characterId: number) =>
    http.post(`/characters/${characterId}/enrich`).then((r) => r.data),
  enrichScene: (sceneId: number) =>
    http.post(`/scenes/${sceneId}/enrich`).then((r) => r.data),
  enrichShot: (shotId: number) =>
    http.post(`/shots/${shotId}/enrich`).then((r) => r.data),
  // 项目级别：兜底扫描所有空白字段
  enrichProject: (projectId: number) =>
    http.post<{ ok: boolean; enriched: { characters: number; scenes: number; shots: number } }>(`/projects/${projectId}/enrich-all`).then((r) => r.data),

  // 修复孤儿 shot 的 scene_id / character_ids 关联
  repairShotRelations: (projectId: number) =>
    http.post<{ scanned: number; orphans: number; fixed_scene: number; fixed_characters: number; details: any[] }>(
      `/projects/${projectId}/canvas/repair-shot-relations`
    ).then((r) => r.data),

  // ============== 批量补全空白字段 ==============
  enrichCharactersBatch: (projectId: number) =>
    http.post<{ ok: boolean; enriched: number; total: number; fields: Record<string, number> }>(`/projects/${projectId}/enrich-characters`).then((r) => r.data),
  enrichScenesBatch: (projectId: number) =>
    http.post<{ ok: boolean; enriched: number; total: number; fields: Record<string, number> }>(`/projects/${projectId}/enrich-scenes`).then((r) => r.data),
  enrichShotsBatch: (projectId: number) =>
    http.post<{ ok: boolean; enriched: number; total: number; fields: Record<string, number> }>(`/projects/${projectId}/enrich-shots`).then((r) => r.data),

  // ============== 批量生成新角色/新场景 ==============
  batchGenerateCharacters: (projectId: number, body: { count?: number; focus?: string } = {}) =>
    http.post<{ ok: boolean; created: number; items: Array<{ id: number; name: string; age: number; gender: string; role: string; alias: string }> }>(
      `/projects/${projectId}/batch-generate-characters`, body
    ).then((r) => r.data),
  batchGenerateScenes: (projectId: number, body: { count?: number; focus?: string } = {}) =>
    http.post<{ ok: boolean; created: number; items: Array<{ id: number; name: string; location: string; time_of_day: string; weather: string }> }>(
      `/projects/${projectId}/batch-generate-scenes`, body
    ).then((r) => r.data),
}

// ============================================================
// 技能社区
// ============================================================
export const skillsApi = {
  list: (params?: { installed_only?: boolean; category?: string }) =>
    http.get<Skill[]>('/skills', { params }).then((r) => r.data),
  toggle: (id: number, installed: boolean) =>
    http.patch<Skill>(`/skills/${id}`, null, { params: { installed } }).then((r) => r.data),
  use: (id: number) => http.post<Skill>(`/skills/${id}/use`).then((r) => r.data),
}

// ============================================================
// 灵感广场（LBP_M TV）
// ============================================================
export const inspirationApi = {
  list: (params?: { category?: string; keyword?: string; tag?: string; featured?: boolean; limit?: number; offset?: number }) =>
    http.get<{ items: Inspiration[]; total: number }>('/inspirations', { params }).then((r) => r.data),
  featured: () => http.get<Inspiration[]>('/inspirations/featured').then((r) => r.data),
  like: (id: number) => http.post<{ ok: boolean; like_count: number }>(`/inspirations/${id}/like`).then((r) => r.data),
  view: (id: number) => http.post<{ ok: boolean }>(`/inspirations/${id}/view`).then((r) => r.data),
  fork: (id: number) => http.post<{ ok: boolean; project_id: number }>(`/inspirations/${id}/fork`).then((r) => r.data),
  publish: (params: {
    project_id: number
    title?: string
    description?: string
    cover_url?: string
    video_url?: string
    category?: string
    tags?: string[]
  }) => http.post<{ ok: boolean; id: number }>('/inspirations', null, { params }).then((r) => r.data),
}

// ============================================================
// 会员 / 积分 / 模型目录 / 画风 / 仪表盘
// ============================================================
export const membershipApi = {
  list: () => http.get<any[]>('/memberships').then((r) => r.data),
}

export const creditsApi = {
  get: () => http.get<any>('/credits').then((r) => r.data),
  signin: () => http.post<{ ok: boolean }>('/credits/signin').then((r) => r.data),
  upgrade: (tier: string) => http.post<{ ok: boolean }>('/credits/upgrade', null, { params: { tier } }).then((r) => r.data),
  transactions: (params?: { limit?: number }) => http.get<any[]>('/credits/transactions', { params }).then((r) => r.data),
}

export const modelsApi = {
  list: (params?: { model_type?: string; vendor?: string }) =>
    http.get<ModelCatalog[]>('/models', { params }).then((r) => r.data),
}

export const artStylesApi = {
  list: (params?: { category?: string }) =>
    http.get<ArtStyle[]>('/art-styles', { params }).then((r) => r.data),
}

export const dashboardApi = {
  stats: () => http.get<DashboardStats>('/dashboard/stats').then((r) => r.data),
}

// ============================================================
// 用户认证（注册/登录/当前用户信息）
// ============================================================
import type { UserInfo } from '@/stores/auth'

export interface TokenOut {
  access_token: string
  token_type: 'bearer'
  user: UserInfo
}

export const authApi = {
  register: (data: { email: string; password: string; display_name: string }) =>
    http.post<TokenOut>('/auth/register', data).then((r) => r.data),
  login: (data: { email: string; password: string }) =>
    http.post<TokenOut>('/auth/login', data).then((r) => r.data),
  me: () => http.get<UserInfo>('/auth/me').then((r) => r.data),
}

// ============================================================
// 媒体编辑（镜头级：消除笔/口型/音频分离/九宫格/全景...）
// 后端参数均为 query
// ============================================================
export const mediaApi = {
  inpaint: (shotId: number, params: { mask_url: string; prompt: string }) =>
    http.post<{ ok: boolean; image_url: string }>(`/shots/${shotId}/inpaint`, null, { params }).then((r) => r.data),
  removeWatermark: (shotId: number) =>
    http.post<{ ok: boolean }>(`/shots/${shotId}/remove-watermark`).then((r) => r.data),
  reAudit: (shotId: number) =>
    http.post<{ ok: boolean }>(`/shots/${shotId}/re-audit`).then((r) => r.data),
  audioSeparate: (shotId: number) =>
    http.post<{ ok: boolean; vocals_url: string; music_url: string; ambient_url: string }>(`/shots/${shotId}/audio-separate`).then((r) => r.data),
  lipsync: (shotId: number, params?: { audio_url?: string; text?: string; voice?: string }) =>
    http.post<{ ok: boolean; video_url: string }>(`/shots/${shotId}/lipsync`, null, { params }).then((r) => r.data),
  tts: (shotId: number, params: { text: string; voice?: string; emotion?: string; language?: string }) =>
    http.post<{ ok: boolean; audio_url: string; duration?: number }>(`/shots/${shotId}/tts`, null, { params }).then((r) => r.data),
  audioTranslate: (shotId: number, params: { target_language?: string }) =>
    http.post<{ ok: boolean; video_url: string; language: string }>(`/shots/${shotId}/audio-translate`, null, { params }).then((r) => r.data),
  headTailFrame: (shotId: number, params: { head_prompt?: string; tail_prompt?: string }) =>
    http.post<{ ok: boolean; head_url?: string; tail_url?: string }>(`/shots/${shotId}/head-tail-frame`, null, { params }).then((r) => r.data),
  extend: (shotId: number, params: { direction?: string; seconds?: number }) =>
    http.post<{ ok: boolean; extend_url: string }>(`/shots/${shotId}/extend`, null, { params }).then((r) => r.data),
  panorama: (sceneId: number) =>
    http.post<{ ok: boolean; panorama_url: string }>(`/scenes/${sceneId}/panorama`).then((r) => r.data),
  grid9: (shotId: number, params: { prompt: string }) =>
    http.post<{ ok: boolean; images: string[] }>(`/shots/${shotId}/grid9`, null, { params }).then((r) => r.data),
}
