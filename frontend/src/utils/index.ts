// 全局工具函数

/** 格式化时长（秒 → "MM:SS"） */
export function formatDuration(sec: number): string {
  if (!sec || sec < 0) return '00:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/** 格式化大数字 (1234 → 1.2k, 1500000 → 1.5M) */
export function formatCount(n: number): string {
  if (n < 1000) return String(n)
  if (n < 1_000_000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'k'
  return (n / 1_000_000).toFixed(1).replace(/\.0$/, '') + 'M'
}

/** 格式化积分 */
export function formatCredits(n: number): string {
  return n.toLocaleString('zh-CN')
}

/** 格式化日期 */
export function formatDate(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** 相对时间 (3小时前) */
export function relativeTime(iso?: string): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return `${sec} 秒前`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day} 天前`
  return formatDate(iso).split(' ')[0]
}

/** 任务状态标签 */
export function taskStatusLabel(status: string): { text: string; type: string } {
  const map: Record<string, { text: string; type: string }> = {
    pending: { text: '等待中', type: 'info' },
    running: { text: '生成中', type: 'warning' },
    success: { text: '已完成', type: 'success' },
    failed: { text: '失败', type: 'danger' },
    cancelled: { text: '已取消', type: 'info' },
  }
  return map[status] || { text: status, type: '' }
}

/** 任务状态图标 */
export function taskStatusIcon(status: string): string {
  const map: Record<string, string> = {
    pending: '🟡',
    running: '🔵',
    success: '🟢',
    failed: '🔴',
    cancelled: '⚪',
  }
  return map[status] || '⚪'
}

/** 项目状态标签 */
export function projectStatusLabel(status: string): { text: string; type: string } {
  const map: Record<string, { text: string; type: string }> = {
    draft: { text: '草稿', type: 'info' },
    running: { text: '进行中', type: 'warning' },
    completed: { text: '已完成', type: 'success' },
    failed: { text: '失败', type: 'danger' },
  }
  return map[status] || { text: status, type: '' }
}

/** 复制到剪贴板 */
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

/** 防抖 */
export function debounce<T extends (...args: any[]) => any>(fn: T, delay = 300) {
  let timer: any = null
  return ((...args: Parameters<T>) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => fn(...args), delay)
  }) as T
}
