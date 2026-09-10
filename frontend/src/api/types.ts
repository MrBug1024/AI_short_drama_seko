// 与后端 Pydantic schema 对齐的类型定义

export interface Project {
  id: number
  name: string
  description: string
  cover_url: string
  status: string
  art_style: string
  target_episodes: number
  target_duration_sec: number
  prompt: string
  created_at: string
  updated_at: string
  // 统计
  episode_count: number
  character_count: number
  scene_count: number
  shot_count: number
  task_count: number
  task_pending: number
}

export interface Episode {
  id: number
  project_id: number
  episode_no: number
  title: string
  synopsis: string
  status: string
  shot_count: number
  created_at: string
  updated_at: string
}

export interface Shot {
  id: number
  project_id: number
  episode_id?: number
  shot_no: number
  shot_code: string
  description: string
  composition: string
  camera_movement: string
  camera_angle: string
  character_ids: number[]
  scene_id?: number
  prop_ids: number[]
  dialogue: string
  narration: string
  duration_sec: number
  visual_prompt: string
  image_url: string
  video_url: string
  audio_url: string
  status: string
}

export interface Character {
  id: number
  project_id: number
  name: string
  alias: string
  age: number
  gender: string
  role: string
  appearance: string
  outfit: string
  personality: string
  backstory: string
  reference_images: string[]
  portrait_url: string
  view_images: Record<string, string>
  consistency_key: string
}

export interface CharacterRelation {
  id: number
  project_id: number
  from_character_id: number
  to_character_id: number
  relation_type: string
  description: string
  from_name?: string
  to_name?: string
}

export interface Scene {
  id: number
  project_id: number
  name: string
  location: string
  time_of_day: string
  weather: string
  mood: string
  description: string
  visual_prompt: string
  reference_images: string[]
  panorama_url: string
}

export interface Prop {
  id: number
  project_id: number
  name: string
  category: string
  description: string
  visual_prompt: string
  reference_images: string[]
}

export interface CanvasNode {
  id: number
  project_id: number
  node_type: string
  ref_id?: number
  title: string
  position_x: number
  position_y: number
  thumbnail_url: string
  status: string
  meta: Record<string, any>
}

export interface CanvasEdge {
  id: number
  project_id: number
  source_id: number
  target_id: number
  edge_type: string
  label: string
}

export interface CanvasSnapshot {
  nodes: CanvasNode[]
  edges: CanvasEdge[]
}

export interface GenerationTask {
  id: number
  project_id: number
  task_type: string
  shot_id?: number
  character_id?: number
  scene_id?: number
  prop_id?: number
  status: string
  progress: number
  phase: string
  prompt: string
  output_url: string
  error_msg: string
  provider_name: string
  model_name: string
  duration_ms: number
  created_at: string
  updated_at: string
  // TaskListItem 扩展
  shot_code?: string
  target_title?: string
}

export interface Skill {
  id: number
  code: string
  name: string
  description: string
  icon: string
  category: string
  installed: boolean
  is_builtin: boolean
  is_official?: boolean
  install_count?: number
  sort_order: number
  usage_count: number
}

export interface Inspiration {
  id: number
  project_id: number
  title: string
  author?: string
  description?: string
  cover_url?: string
  video_url?: string
  category?: string
  tags?: string[]
  view_count: number
  like_count: number
  fork_count: number
  is_featured: boolean
  source_skill?: string
  art_style?: string
  created_at: string
}

export interface ModelCatalog {
  id: number
  code: string
  name: string
  vendor: string
  icon?: string
  model_type: 'video' | 'image' | 'audio'
  description?: string
  features?: string[]
  specs?: Record<string, any>
  credits_per_second: number
  credits_per_image: number
  is_premium: boolean
  is_recommended: boolean
}

export interface ArtStyle {
  id: number
  code: string
  name: string
  category: string
  description?: string
  visual_prompt?: string
  cover_url?: string
  tags?: string[]
  is_new: boolean
}

export interface DashboardStats {
  projects: number
  episodes: number
  tasks: number
  tasks_running: number
  inspirations: number
  credits: number
  tier: string
}
