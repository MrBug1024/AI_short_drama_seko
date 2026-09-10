<template>
  <div class="fixed inset-0 bg-ink-950 flex flex-col overflow-hidden select-none">
    <!-- 顶部工具栏 -->
    <header class="h-12 shrink-0 bg-black border-b border-ink-800 flex items-center px-3 gap-2 z-30">
      <button class="w-8 h-8 rounded-lg hover:bg-ink-800 flex items-center justify-center text-slate-300" @click="$router.push('/projects')">
        <el-icon :size="16"><ArrowLeft /></el-icon>
      </button>
      <div class="text-sm font-medium text-white truncate max-w-[220px] shrink min-w-0">{{ project?.name || '加载中...' }}</div>
      <span v-if="project" class="text-xs text-slate-500 hidden lg:inline whitespace-nowrap">
        {{ project.episode_count }} 集 · {{ project.shot_count }} 分镜
      </span>

      <div class="flex-1" />

      <!-- 剧本优化 / 角色关系 -->
      <button class="lbp-btn-ghost !py-1.5 text-xs !rounded-full whitespace-nowrap shrink-0" @click="openScriptPanel">
        <el-icon :size="13"><Document /></el-icon>
        剧本 / 关系
      </button>

      <!-- AI 自动策划 -->
      <button class="lbp-btn-primary !py-1.5 text-xs whitespace-nowrap shrink-0" :disabled="planning" @click="aiPlan">
        <el-icon v-if="planning" class="animate-spin" :size="13"><Loading /></el-icon>
        <el-icon v-else :size="13"><MagicStick /></el-icon>
        {{ planning ? 'AI 策划中...' : 'AI 自动策划' }}
      </button>

      <!-- 批量操作 -->
      <el-dropdown trigger="click" @command="onBatchCommand">
        <button class="lbp-btn-ghost !py-1.5 text-xs !rounded-full whitespace-nowrap shrink-0">
          <el-icon :size="13"><Grid /></el-icon>
          批量生成
          <el-icon :size="11"><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="images">批量生成分镜图</el-dropdown-item>
            <el-dropdown-item command="videos">批量生成分镜视频</el-dropdown-item>
            <el-dropdown-item command="compose">合成完整视频</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <!-- 自动布局 -->
      <button class="lbp-btn-ghost !py-1.5 text-xs !rounded-full whitespace-nowrap shrink-0" @click="autoLayout">
        <el-icon :size="13"><MagicStick /></el-icon>
        自动布局
      </button>

      <!-- 缩放 -->
      <div class="flex items-center gap-1 bg-ink-850 border border-ink-700 rounded-full px-1 py-0.5 shrink-0">
        <button class="w-6 h-6 rounded-full hover:bg-ink-700 text-slate-300 flex items-center justify-center" @click="zoomBy(-0.15)">
          <el-icon :size="12"><Minus /></el-icon>
        </button>
        <span class="text-xs text-slate-400 w-10 text-center">{{ Math.round(scale * 100) }}%</span>
        <button class="w-6 h-6 rounded-full hover:bg-ink-700 text-slate-300 flex items-center justify-center" @click="zoomBy(0.15)">
          <el-icon :size="12"><Plus /></el-icon>
        </button>
        <button class="w-6 h-6 rounded-full hover:bg-ink-700 text-slate-400 flex items-center justify-center" title="适应画布" @click="fitView">
          <el-icon :size="12"><FullScreen /></el-icon>
        </button>
      </div>
    </header>

    <!-- 画布主体 -->
    <div
      ref="viewportRef"
      class="flex-1 relative overflow-hidden dot-grid cursor-grab active:cursor-grabbing"
      @mousedown="onPanStart"
      @click="onViewportClick"
      @wheel.prevent="onWheel"
    >
      <!-- 变换层 -->
      <div
        class="absolute top-0 left-0 origin-top-left"
        :style="{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${scale})` }"
      >
        <!-- 连线层 -->
        <svg class="absolute top-0 left-0 overflow-visible" width="1" height="1" style="pointer-events: none">
          <defs>
            <marker id="cv-arrow-ref" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0.8 L 7 4 L 0 7.2 z" fill="rgba(45,224,200,0.55)" />
            </marker>
            <marker id="cv-arrow-ref-hl" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
              <path d="M 0 0.8 L 7 4 L 0 7.2 z" fill="rgb(94,234,212)" />
            </marker>
            <marker id="cv-arrow-rel" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0.8 L 7 4 L 0 7.2 z" fill="rgba(244,114,182,0.7)" />
            </marker>
          </defs>

          <!-- 引用边（分镜→角色/场景） -->
          <g v-for="g in refEdgeGeoms" :key="'ref-' + g.key">
            <!-- 加宽的透明命中区域 -->
            <path :d="g.d" fill="none" stroke="transparent" stroke-width="12" style="pointer-events: stroke; cursor: pointer"
              @mouseenter="hoverEdgeKey = g.key" @mouseleave="hoverEdgeKey = ''" />
            <path
              :d="g.d"
              fill="none"
              :stroke="g.dim ? 'rgba(45,224,200,0.10)' : (g.active ? 'rgba(94,234,212,0.9)' : 'rgba(45,224,200,0.32)')"
              :stroke-width="g.active ? 2.2 : 1.4"
              :stroke-dasharray="g.active ? '' : '5 5'"
              :marker-end="g.active ? 'url(#cv-arrow-ref-hl)' : 'url(#cv-arrow-ref)'"
              class="transition-all duration-200"
              style="pointer-events: none"
            />
          </g>

          <!-- 角色关系边（实线+标签+类型配色） -->
          <g v-for="g in relEdgeGeoms" :key="'rel-' + g.key">
            <path :d="g.d" fill="none" stroke="transparent" stroke-width="14" style="pointer-events: stroke; cursor: pointer"
              @mouseenter="hoverEdgeKey = g.key" @mouseleave="hoverEdgeKey = ''" />
            <path
              :d="g.d"
              fill="none"
              :stroke="g.dim ? g.colorDim : g.color"
              :stroke-width="g.active ? 3 : 2"
              stroke-linecap="round"
              :marker-end="'url(#cv-arrow-rel)'"
              class="transition-all duration-200"
              style="pointer-events: none"
              :opacity="g.dim ? 0.25 : 1"
            />
            <!-- 关系标签（中点胶囊） -->
            <g v-if="g.label && !g.dim" style="pointer-events: none">
              <rect
                :x="g.labelX - g.labelW / 2" :y="g.labelY - 9"
                :width="g.labelW" height="18" rx="9"
                :fill="g.active ? 'rgb(30 30 30)' : 'rgb(16 16 16)'"
                :stroke="g.color" stroke-width="1" :opacity="g.active ? 1 : 0.9"
              />
              <text
                :x="g.labelX" :y="g.labelY + 4"
                text-anchor="middle" font-size="10" :fill="g.color"
                style="user-select: none"
              >{{ g.label }}</text>
            </g>
          </g>
        </svg>

        <!-- 节点 -->
        <div
          v-for="n in nodes"
          :key="n.id"
          class="absolute group cursor-move rounded-xl bg-ink-850/95 border overflow-hidden transition-all duration-200"
          :class="[
            selectedId === n.id
              ? 'border-brand-400/70 shadow-glow-brand'
              : dimmedNodes.has(n.id)
                ? 'border-ink-800 opacity-35'
                : 'border-ink-700/60 hover:border-brand-500/50 hover:shadow-card hover:-translate-y-0.5',
            n.status === 'running' ? 'cv-node-running' : '',
          ]"
          :style="{ left: n.position_x + 'px', top: n.position_y + 'px', width: NODE_W + 'px' }"
          @mousedown.stop="onNodeDragStart($event, n)"
          @click.stop="selectedId = n.id"
          @dblclick.stop="onNodeDblClick(n)"
        >
          <!-- 类型色条 -->
          <div class="absolute left-0 top-0 bottom-0 w-[3px]" :style="{ background: nodeTypeColor(n.node_type) }" />

          <!-- 头部：类型徽标 + 菜单 -->
          <div class="flex items-center justify-between px-2.5 pt-2 pl-3">
            <span
              class="text-[10px] px-1.5 py-0.5 rounded-md border flex items-center gap-1"
              :style="{ color: nodeTypeColor(n.node_type), borderColor: nodeTypeColor(n.node_type) + '44', background: nodeTypeColor(n.node_type) + '14' }"
            >
              <el-icon :size="9"><component :is="nodeIcon(n.node_type)" /></el-icon>
              {{ nodeTypeLabel(n.node_type) }}
            </span>
            <el-dropdown trigger="click" @command="(cmd: string) => onNodeCommand(cmd, n)">
              <button class="w-5 h-5 rounded hover:bg-ink-700 text-slate-400 flex items-center justify-center opacity-0 group-hover:opacity-100 transition" @mousedown.stop>
                <el-icon :size="12"><MoreFilled /></el-icon>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-for="a in nodeActions(n)" :key="a.cmd" :command="a.cmd">
                    {{ a.label }}
                  </el-dropdown-item>
                  <el-dropdown-item command="__delete" divided class="!text-red-400">删除节点</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>

          <!-- 缩略图 -->
          <div class="mx-2.5 mt-2 rounded-lg overflow-hidden bg-ink-800 aspect-video relative">
            <img v-if="n.thumbnail_url" :src="n.thumbnail_url" class="w-full h-full object-cover" draggable="false" />
            <div v-else class="w-full h-full flex items-center justify-center">
              <el-icon :size="20" class="text-slate-600"><component :is="nodeIcon(n.node_type)" /></el-icon>
            </div>
            <!-- 生成中遮罩：呼吸 + 转圈 -->
            <div v-if="n.status === 'running'" class="absolute inset-0 bg-black/55 flex flex-col items-center justify-center gap-1.5">
              <el-icon class="animate-spin text-brand-400" :size="18"><Loading /></el-icon>
              <span class="text-[10px] text-brand-300">生成中…</span>
            </div>
            <!-- 视频可预览：播放按钮遮罩（点击播放） -->
            <div
              v-if="nodeVideoUrl(n) && n.status !== 'running'"
              class="absolute inset-0 bg-black/25 hover:bg-black/45 flex items-center justify-center cursor-pointer transition group/play"
              @click.stop="openVideoPreview(n)"
              @dblclick.stop
            >
              <span class="w-9 h-9 rounded-full bg-black/60 border border-white/25 flex items-center justify-center group-hover/play:scale-110 group-hover/play:bg-brand-500/90 transition">
                <el-icon :size="16" class="text-white ml-0.5"><VideoPlay /></el-icon>
              </span>
              <span class="absolute bottom-1 left-1.5 text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/90 text-black font-semibold">视频就绪</span>
            </div>
            <!-- 视频标记 -->
            <span v-if="n.node_type === 'video'" class="absolute bottom-1 right-1 w-5 h-5 rounded-full bg-black/60 flex items-center justify-center">
              <el-icon :size="10" class="text-white"><VideoPlay /></el-icon>
            </span>
            <!-- 完成角标 -->
            <span v-if="n.thumbnail_url && n.status !== 'running'" class="absolute top-1 right-1 w-4 h-4 rounded-full bg-brand-500/90 flex items-center justify-center opacity-0 group-hover:opacity-100 transition">
              <svg viewBox="0 0 12 12" class="w-2.5 h-2.5 fill-none stroke-black stroke-2"><path d="M2 6.5 L4.8 9 L10 3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </span>
          </div>

          <!-- 标题区：按节点类型展示不同字段 -->
          <div class="px-2.5 py-2 pl-3 space-y-0.5">
            <!-- 角色：名字 + 别名 -->
            <template v-if="n.node_type === 'character'">
              <div class="text-xs font-medium text-slate-100 line-clamp-1" :title="n.meta?.name || n.title">
                {{ n.meta?.name || n.title || '未命名角色' }}
              </div>
              <div v-if="n.meta?.alias" class="text-[10px] text-slate-500 line-clamp-1" :title="n.meta.alias">
                别名：{{ n.meta.alias }}
              </div>
            </template>

            <!-- 场景：场景名 + 地点 -->
            <template v-else-if="n.node_type === 'scene'">
              <div class="text-xs font-medium text-slate-100 line-clamp-1" :title="n.meta?.name || n.title">
                {{ n.meta?.name || n.title || '未命名场景' }}
              </div>
              <div v-if="n.meta?.location" class="text-[10px] text-slate-500 line-clamp-1" :title="n.meta.location">
                📍 {{ n.meta.location }}
              </div>
            </template>

            <!-- 分镜：编号 + 描述 -->
            <template v-else-if="n.node_type === 'shot'">
              <div class="text-xs font-medium text-slate-100 line-clamp-1" :title="n.meta?.shot_code || n.title">
                {{ n.meta?.shot_code || n.title || '分镜' }}
              </div>
              <div v-if="n.meta?.description" class="text-[10px] text-slate-500 line-clamp-2" :title="n.meta.description">
                {{ n.meta.description }}
              </div>
            </template>

            <!-- 其它节点（剧本/分镜表/视频...）：沿用原 title -->
            <template v-else>
              <div class="text-xs text-slate-200 line-clamp-1" :title="n.title">
                {{ n.title || nodeTypeLabel(n.node_type) }}
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- 空态 -->
      <div v-if="!loading && !nodes.length" class="absolute inset-0 flex flex-col items-center justify-center text-center pointer-events-none">
        <el-icon :size="44" class="text-slate-700"><Connection /></el-icon>
        <div class="text-slate-500 text-sm mt-4">画布还是空的</div>
        <div class="text-slate-600 text-xs mt-1">点击右上角「AI 自动策划」，输入灵感一键生成分镜节点</div>
      </div>
    </div>

    <!-- 底部状态栏 -->
    <footer class="h-8 shrink-0 bg-black border-t border-ink-800 flex items-center px-4 gap-4 text-[11px] text-slate-500 z-30">
      <span>节点 {{ nodes.length }}</span>
      <span>引用 {{ edges.length }}</span>
      <span v-if="relations.length">关系 {{ relations.length }}</span>
      <span v-if="runningTasks > 0" class="text-brand-400 flex items-center gap-1">
        <el-icon class="animate-spin" :size="11"><Loading /></el-icon>
        {{ runningTasks }} 个任务生成中
      </span>
      <div class="flex-1" />
      <span v-if="selectedId !== null" class="text-slate-600">已选中节点 · 无关节点已淡化 · 点击空白取消</span>
      <span>滚轮缩放 · 拖拽空白平移 · 拖拽节点移动 · 双击节点打开设计</span>
    </footer>

    <!-- 视频生成模型选择弹窗 -->
    <el-dialog v-model="videoDialog.visible" title="视频生成" width="380px" append-to-body>
      <div class="space-y-3">
        <div>
          <div class="text-xs text-slate-400 mb-1.5">选择模型</div>
          <el-select v-model="videoDialog.model" class="w-full">
            <el-option v-for="m in videoModels" :key="m.code" :label="m.name" :value="m.code" />
          </el-select>
        </div>
        <div class="text-xs text-slate-500">
          将基于节点「{{ videoDialog.title }}」的分镜图生成视频
        </div>
      </div>
      <template #footer>
        <button class="lbp-btn-ghost !py-1.5 text-xs" @click="videoDialog.visible = false">取消</button>
        <button class="lbp-btn-primary !py-1.5 text-xs" :disabled="videoDialog.busy" @click="confirmVideoGen">
          {{ videoDialog.busy ? '生成中...' : '开始生成' }}
        </button>
      </template>
    </el-dialog>

    <!-- ============ 视频预览弹窗（支持全屏播放） ============ -->
    <el-dialog
      v-model="videoPreview.visible"
      :title="`视频预览 · ${videoPreview.title}`"
      width="760px"
      append-to-body
      destroy-on-close
      class="cv-video-dialog"
      @closed="onVideoPreviewClosed"
    >
      <div class="rounded-lg overflow-hidden bg-black relative" id="cv-video-wrap">
        <video
          ref="videoPreviewRef"
          :src="videoPreview.url"
          class="w-full max-h-[60vh] block"
          controls
          autoplay
          loop
          playsinline
          controlslist="nodownload"
          @canplay="tryAutoPlay"
        />
      </div>
      <div class="flex items-center gap-2 mt-3 text-xs text-slate-400">
        <el-icon :size="12"><VideoPlay /></el-icon>
        <span class="truncate flex-1" :title="videoPreview.url">{{ videoPreview.url }}</span>
        <a
          :href="videoPreview.url"
          download
          class="lbp-btn-ghost !px-2 !py-1 text-[11px] shrink-0"
          title="下载视频文件"
        >下载</a>
        <button class="lbp-btn-primary !px-2.5 !py-1 text-[11px] shrink-0" @click="toggleFullscreen">
          <el-icon :size="11"><FullScreen /></el-icon>
          {{ videoPreview.isFullscreen ? '退出全屏' : '全屏播放' }}
        </button>
      </div>
    </el-dialog>

    <!-- ============ 节点设计面板（角色/场景/分镜/剧本） ============ -->
    <el-drawer
      v-model="designPanel.visible"
      :title="designPanel.title"
      direction="rtl"
      size="440px"
      append-to-body
      class="lbp-design-drawer"
    >
      <!-- 角色设计 -->
      <div v-if="designPanel.type === 'character' && designPanel.character" class="space-y-4">
        <!-- 多视图设计稿画廊 -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-medium text-slate-300">角色设计稿（多视图）</span>
            <button class="lbp-btn-primary !py-1 text-[11px]" :disabled="designPanel.busy" @click="genDesignSheet">
              <el-icon v-if="designPanel.busy" class="animate-spin" :size="11"><Loading /></el-icon>
              <el-icon v-else :size="11"><MagicStick /></el-icon>
              生成设计稿
            </button>
          </div>
          <div class="grid grid-cols-3 gap-2">
            <div
              v-for="v in CHAR_VIEWS"
              :key="v.key"
              class="relative aspect-square rounded-lg overflow-hidden bg-ink-800 border border-ink-700 cursor-pointer group"
              @click="regenView(v.key)"
            >
              <img v-if="designPanel.character.view_images?.[v.key]" :src="designPanel.character.view_images[v.key]" class="w-full h-full object-cover" />
              <div v-else class="w-full h-full flex flex-col items-center justify-center text-slate-600">
                <el-icon :size="18"><User /></el-icon>
                <span class="text-[10px] mt-1">点击生成</span>
              </div>
              <span class="absolute bottom-0 inset-x-0 bg-black/60 text-[10px] text-center text-slate-300 py-0.5">{{ v.label }}</span>
              <span v-if="designPanel.character.view_images?.[v.key]" class="absolute top-1 right-1 text-[9px] bg-black/60 text-slate-400 rounded px-1 opacity-0 group-hover:opacity-100">重roll</span>
            </div>
          </div>
        </div>

        <!-- 角色设定表单 -->
        <div class="space-y-2.5">
          <div class="text-xs font-medium text-slate-300">角色设定</div>
          <el-input v-model="designPanel.character.name" placeholder="姓名" size="small" />
          <div class="grid grid-cols-2 gap-2">
            <el-input v-model="designPanel.character.alias" placeholder="别名" size="small" />
            <el-input v-model.number="designPanel.character.age" placeholder="年龄" size="small" type="number" />
          </div>
          <div class="grid grid-cols-2 gap-2">
            <el-select v-model="designPanel.character.gender" placeholder="性别" size="small">
              <el-option label="男" value="男" /><el-option label="女" value="女" /><el-option label="其他" value="其他" />
            </el-select>
            <el-select v-model="designPanel.character.role" placeholder="角色定位" size="small">
              <el-option label="主角" value="主角" /><el-option label="配角" value="配角" /><el-option label="反派" value="反派" />
            </el-select>
          </div>
          <el-input v-model="designPanel.character.appearance" type="textarea" :rows="3" placeholder="外貌描述（发型/脸型/五官/体型，越具体生成越准）" size="small" />
          <el-input v-model="designPanel.character.outfit" type="textarea" :rows="2" placeholder="服装（款式+颜色）" size="small" />
          <el-input v-model="designPanel.character.personality" type="textarea" :rows="2" placeholder="性格" size="small" />
          <el-input v-model="designPanel.character.backstory" type="textarea" :rows="2" placeholder="背景故事" size="small" />
          <div class="flex gap-2">
            <button class="lbp-btn-ghost flex-1 !py-1.5 text-xs" :disabled="designPanel.busy" @click="saveCharacter">保存设定</button>
          </div>
        </div>

        <!-- AI 优化 -->
        <div class="space-y-2 pt-2 border-t border-ink-800">
          <div class="text-xs font-medium text-slate-300">AI 优化角色</div>
          <el-input v-model="designPanel.requirement" type="textarea" :rows="2" placeholder="例如：让她看起来更成熟一些，换成红色长裙" size="small" />
          <button class="lbp-btn-primary w-full !py-1.5 text-xs" :disabled="designPanel.busy || !designPanel.requirement" @click="optimizeEntity">
            <el-icon v-if="designPanel.busy" class="animate-spin" :size="11"><Loading /></el-icon>
            <el-icon v-else :size="11"><MagicStick /></el-icon>
            AI 优化并保存
          </button>
        </div>
      </div>

      <!-- 场景设计 -->
      <div v-else-if="designPanel.type === 'scene' && designPanel.scene" class="space-y-4">
        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-medium text-slate-300">场景概念图</span>
            <button class="lbp-btn-primary !py-1 text-[11px]" :disabled="designPanel.busy" @click="genSceneImage">
              <el-icon v-if="designPanel.busy" class="animate-spin" :size="11"><Loading /></el-icon>
              <el-icon v-else :size="11"><MagicStick /></el-icon>
              生成场景图
            </button>
          </div>
          <div class="aspect-video rounded-lg overflow-hidden bg-ink-800 border border-ink-700">
            <img v-if="designPanel.scene.panorama_url" :src="designPanel.scene.panorama_url" class="w-full h-full object-cover" />
            <div v-else class="w-full h-full flex items-center justify-center text-slate-600 text-xs">暂无场景图</div>
          </div>
        </div>
        <div class="space-y-2.5">
          <div class="text-xs font-medium text-slate-300">场景设定</div>
          <el-input v-model="designPanel.scene.name" placeholder="场景名" size="small" />
          <div class="grid grid-cols-2 gap-2">
            <el-input v-model="designPanel.scene.location" placeholder="地点" size="small" />
            <el-select v-model="designPanel.scene.time_of_day" placeholder="时间" size="small">
              <el-option label="白天" value="day" /><el-option label="黄昏" value="dusk" />
              <el-option label="夜晚" value="night" /><el-option label="清晨" value="dawn" />
            </el-select>
          </div>
          <el-input v-model="designPanel.scene.description" type="textarea" :rows="2" placeholder="场景描述" size="small" />
          <el-input v-model="designPanel.scene.visual_prompt" type="textarea" :rows="2" placeholder="视觉提示词（空间+物件+光线+色调）" size="small" />
          <button class="lbp-btn-ghost w-full !py-1.5 text-xs" :disabled="designPanel.busy" @click="saveScene">保存设定</button>
        </div>
        <div class="space-y-2 pt-2 border-t border-ink-800">
          <div class="text-xs font-medium text-slate-300">AI 优化场景</div>
          <el-input v-model="designPanel.requirement" type="textarea" :rows="2" placeholder="例如：改成雨夜，增加霓虹灯反光" size="small" />
          <button class="lbp-btn-primary w-full !py-1.5 text-xs" :disabled="designPanel.busy || !designPanel.requirement" @click="optimizeEntity">
            <el-icon v-if="designPanel.busy" class="animate-spin" :size="11"><Loading /></el-icon>
            <el-icon v-else :size="11"><MagicStick /></el-icon>
            AI 优化并保存
          </button>
        </div>
      </div>

      <!-- 分镜设计 -->
      <div v-else-if="designPanel.type === 'shot' && designPanel.shot" class="space-y-4">
        <div>
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-medium text-slate-300">分镜图</span>
            <button class="lbp-btn-primary !py-1 text-[11px]" :disabled="designPanel.busy" @click="genShotImage">
              <el-icon v-if="designPanel.busy" class="animate-spin" :size="11"><Loading /></el-icon>
              <el-icon v-else :size="11"><MagicStick /></el-icon>
              生成分镜图
            </button>
          </div>
          <div class="aspect-video rounded-lg overflow-hidden bg-ink-800 border border-ink-700">
            <img v-if="designPanel.shot.image_url" :src="designPanel.shot.image_url" class="w-full h-full object-cover" />
            <div v-else class="w-full h-full flex items-center justify-center text-slate-600 text-xs">暂无分镜图</div>
          </div>
        </div>
        <!-- 已生成视频预览 -->
        <div v-if="designPanel.shot.video_url">
          <div class="flex items-center justify-between mb-2">
            <span class="text-xs font-medium text-emerald-400 flex items-center gap-1">
              <el-icon :size="12"><VideoPlay /></el-icon> 生成的视频
            </span>
            <button class="lbp-btn-ghost !px-2 !py-0.5 text-[11px]" @click="openShotVideoPreview(designPanel.shot)">
              <el-icon :size="11"><FullScreen /></el-icon> 全屏预览
            </button>
          </div>
          <div class="aspect-video rounded-lg overflow-hidden bg-black border border-ink-700">
            <video :src="designPanel.shot.video_url" class="w-full h-full object-contain" controls playsinline controlslist="nodownload" />
          </div>
        </div>
        <div class="space-y-2.5">
          <div class="text-xs font-medium text-slate-300">镜头设定</div>
          <el-input v-model="designPanel.shot.description" type="textarea" :rows="2" placeholder="画面描述（谁在做什么）" size="small" />
          <div class="grid grid-cols-2 gap-2">
            <el-input v-model="designPanel.shot.composition" placeholder="构图" size="small" />
            <el-input v-model="designPanel.shot.camera_movement" placeholder="运镜" size="small" />
          </div>
          <div class="grid grid-cols-2 gap-2">
            <el-input v-model="designPanel.shot.camera_angle" placeholder="角度/景别" size="small" />
            <el-input v-model.number="designPanel.shot.duration_sec" placeholder="时长(秒)" size="small" type="number" />
          </div>
          <el-input v-model="designPanel.shot.dialogue" type="textarea" :rows="2" placeholder="台词" size="small" />
          <button class="lbp-btn-ghost w-full !py-1.5 text-xs" :disabled="designPanel.busy" @click="saveShot">保存设定</button>
        </div>
        <div class="space-y-2 pt-2 border-t border-ink-800">
          <div class="text-xs font-medium text-slate-300">AI 优化分镜</div>
          <el-input v-model="designPanel.requirement" type="textarea" :rows="2" placeholder="例如：加强紧张感，改成手持晃动镜头" size="small" />
          <button class="lbp-btn-primary w-full !py-1.5 text-xs" :disabled="designPanel.busy || !designPanel.requirement" @click="optimizeEntity">
            <el-icon v-if="designPanel.busy" class="animate-spin" :size="11"><Loading /></el-icon>
            <el-icon v-else :size="11"><MagicStick /></el-icon>
            AI 优化并保存
          </button>
        </div>
      </div>

      <!-- 剧本设计 -->
      <div v-else-if="designPanel.type === 'script'" class="space-y-4">
        <!-- ============ 完整剧本展示（持久化的脚本实体） ============ -->
        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium text-slate-300">完整剧本</span>
            <span v-if="scriptVersions.total" class="text-[10px] text-slate-500">v{{ scriptVersions.current_version }} · {{ scriptVersions.total }} 个版本</span>
          </div>
          <div v-if="scriptVersions.loading" class="text-[11px] text-slate-500 py-2">加载中…</div>
          <div v-else-if="!scriptVersions.items.length" class="text-[11px] text-slate-600 py-3 text-center bg-ink-850 rounded-lg border border-ink-800">
            <p>尚未保存剧本。</p>
            <p class="mt-1.5 text-slate-500">请回「我的项目」点击「开始创作」填写剧本，剧本将作为项目核心资产持久保存。</p>
          </div>
          <div v-else class="space-y-2">
            <div v-for="sv in scriptVersions.items" :key="sv.id" class="bg-ink-850 rounded-lg border border-ink-800 overflow-hidden">
              <div class="flex items-center justify-between px-3 py-2 bg-ink-800/50">
                <div class="flex items-center gap-2 min-w-0">
                  <span class="text-[10px] px-1.5 py-0.5 rounded bg-brand-500/15 text-brand-300 border border-brand-500/30 shrink-0">v{{ sv.version }}</span>
                  <span class="text-xs text-slate-100 truncate" :title="sv.title">{{ sv.title || '未命名剧本' }}</span>
                </div>
                <span class="text-[10px] text-slate-500 shrink-0">{{ formatScriptDate(sv.updated_at) }}</span>
              </div>
              <div v-if="sv.logline" class="px-3 py-2 text-[11px] text-slate-400 border-b border-ink-800">
                <span class="text-slate-500">梗概：</span>{{ sv.logline }}
              </div>
              <!-- 当前激活版本：可编辑；其他版本：只读 -->
              <div v-if="editingScriptId === sv.id" class="px-3 py-2 border-b border-ink-800 space-y-2">
                <el-input v-model="editingScript.title" placeholder="剧名" size="small" />
                <el-input v-model="editingScript.logline" type="textarea" :rows="2" placeholder="一句话梗概" size="small" />
                <el-input v-model="editingScript.content" type="textarea" :rows="8" placeholder="完整剧本（剧情剧本 / 旁白 / 分镜表均可）" size="small" resize="vertical" />
                <div class="flex gap-2">
                  <button class="lbp-btn-ghost flex-1 !py-1 text-[11px]" @click="cancelEditScript">取消</button>
                  <button class="lbp-btn-primary flex-1 !py-1 text-[11px]" :disabled="scriptSaving" @click="saveEditScript(sv.id)">
                    <el-icon v-if="scriptSaving" class="animate-spin" :size="11"><Loading /></el-icon>
                    保存剧本
                  </button>
                </div>
              </div>
              <!-- 只读视图 -->
              <div v-else class="px-3 py-2 max-h-64 overflow-y-auto">
                <pre class="text-[11px] text-slate-300 whitespace-pre-wrap font-mono leading-relaxed m-0">{{ sv.content }}</pre>
              </div>
              <!-- 版本操作按钮 -->
              <div class="flex items-center gap-2 px-3 py-2 bg-ink-800/30 border-t border-ink-800">
                <button v-if="editingScriptId !== sv.id" class="text-[11px] text-brand-400 hover:underline" @click="startEditScript(sv)">
                  编辑剧本
                </button>
                <button class="text-[11px] text-emerald-400 hover:underline" :disabled="applyingScriptId === sv.id" @click="applyScript(sv.id)">
                  <el-icon v-if="applyingScriptId === sv.id" class="animate-spin" :size="11"><Loading /></el-icon>
                  重新应用到画布
                </button>
                <span class="text-[10px] text-slate-600 ml-auto">应用于画布 → 重新解析角色/场景/分镜</span>
              </div>
            </div>
          </div>
        </div>

        <div class="space-y-2 pt-3 border-t border-ink-800">
          <div class="text-xs font-medium text-slate-300">AI 优化整部剧本</div>
          <div class="text-[11px] text-slate-500">按你的要求改写剧本（生成新版本，旧版本永久保留，可回滚）</div>
          <el-input v-model="designPanel.requirement" type="textarea" :rows="4" placeholder="例如：把结局改成反转，女主其实是卧底；加强第 3-5 镜的冲突" size="small" />
          <button class="lbp-btn-primary w-full !py-1.5 text-xs" :disabled="designPanel.busy || !designPanel.requirement" @click="optimizeScript">
            <el-icon v-if="designPanel.busy" class="animate-spin" :size="11"><Loading /></el-icon>
            <el-icon v-else :size="11"><MagicStick /></el-icon>
            AI 优化剧本（生成新版本 v+1）
          </button>
        </div>

        <!-- 角色关系管理 -->
        <div class="space-y-2 pt-3 border-t border-ink-800">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium text-slate-300">角色关系</span>
            <button class="lbp-btn-ghost !py-1 text-[11px]" :disabled="designPanel.busy" @click="autoRelations">
              <el-icon :size="11"><MagicStick /></el-icon> AI 自动设计
            </button>
          </div>
          <div v-if="!relations.length" class="text-[11px] text-slate-600 py-2 text-center">暂无关系，点击「AI 自动设计」生成</div>
          <div v-for="r in relations" :key="r.id" class="flex items-center gap-2 bg-ink-850 rounded-lg px-2.5 py-2 border border-ink-800">
            <span class="text-xs text-slate-200">{{ r.from_name }}</span>
            <span class="text-[10px] px-1.5 py-0.5 rounded bg-brand-500/10 text-brand-300 border border-brand-500/30 shrink-0">{{ r.relation_type }}</span>
            <span class="text-xs text-slate-200">{{ r.to_name }}</span>
            <div class="flex-1" />
            <button class="text-slate-600 hover:text-red-400" @click="removeRelation(r.id)">
              <el-icon :size="12"><Close /></el-icon>
            </button>
          </div>
          <!-- 手动添加关系 -->
          <div class="flex gap-1.5 pt-1">
            <el-select v-model="newRelation.from" placeholder="角色A" size="small" class="flex-1">
              <el-option v-for="c in charOptions" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
            <el-select v-model="newRelation.type" placeholder="关系" size="small" class="flex-1">
              <el-option v-for="t in RELATION_TYPES" :key="t" :label="t" :value="t" />
            </el-select>
            <el-select v-model="newRelation.to" placeholder="角色B" size="small" class="flex-1">
              <el-option v-for="c in charOptions" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
            <button class="lbp-btn-ghost !px-2 !py-1 text-xs shrink-0" :disabled="!newRelation.from || !newRelation.to" @click="addRelation">+</button>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  ArrowLeft, ArrowDown, Loading, MagicStick, Grid, Minus, Plus, FullScreen,
  MoreFilled, VideoPlay, Connection, User, Place, Film, Document, Headset, Close,
} from '@element-plus/icons-vue'
import { projectsApi, canvasApi, assetsApi, tasksApi, modelsApi, mediaApi, designApi, scriptsApi } from '@/api'
import type { ScriptVersion } from '@/api'
import type { Project, CanvasNode, CanvasEdge, ModelCatalog, Shot, Character, Scene, CharacterRelation } from '@/api/types'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.id)

const NODE_W = 208
const NODE_H = 172

// ============ 状态 ============
const project = ref<Project | null>(null)
const nodes = ref<CanvasNode[]>([])
const edges = ref<CanvasEdge[]>([])
const loading = ref(true)
const planning = ref(false)
const selectedId = ref<number | null>(null)
const hoverEdgeKey = ref('')
const runningTasks = ref(0)
const videoModels = ref<ModelCatalog[]>([])

// 视图变换
const viewportRef = ref<HTMLElement | null>(null)
const scale = ref(0.9)
const pan = reactive({ x: 60, y: 40 })

// ============ 加载 ============
const loadAll = async () => {
  const [p, snap] = await Promise.all([
    projectsApi.get(projectId),
    canvasApi.snapshot(projectId),
  ])
  project.value = p
  nodes.value = snap.nodes
  edges.value = snap.edges
  // 角色关系（用于画布关系连线）
  relations.value = await designApi.listRelations(projectId).catch(() => [])

  // 画布为空但有资产 → 自动从实体构建节点
  if (!nodes.value.length && (p.character_count + p.scene_count + p.shot_count) > 0) {
    await buildNodesFromEntities()
  }
}

// 从角色/场景/分镜自动构建画布节点
const buildNodesFromEntities = async () => {
  const [chars, scenes, shots] = await Promise.all([
    assetsApi.characters(projectId),
    assetsApi.scenes(projectId),
    assetsApi.shots(projectId),
  ])

  const created: CanvasNode[] = []
  let x = 0
  // 角色行
  for (const c of chars) {
    const n = await canvasApi.createNode(projectId, {
      node_type: 'character', ref_id: c.id, title: c.name,
      position_x: x, position_y: 0, thumbnail_url: c.portrait_url,
    })
    created.push(n)
    x += NODE_W + 60
  }
  // 场景行
  x = 0
  for (const s of scenes) {
    const n = await canvasApi.createNode(projectId, {
      node_type: 'scene', ref_id: s.id, title: s.name,
      position_x: x, position_y: NODE_H + 80, thumbnail_url: s.panorama_url,
    })
    created.push(n)
    x += NODE_W + 60
  }
  // 分镜行
  x = 0
  for (const sh of shots) {
    const n = await canvasApi.createNode(projectId, {
      node_type: 'shot', ref_id: sh.id, title: `${sh.shot_code || 'SC' + sh.shot_no} ${sh.description.slice(0, 12)}`,
      position_x: x, position_y: (NODE_H + 80) * 2, thumbnail_url: sh.image_url,
      meta: { status: sh.status, video_url: sh.video_url || '' },
    })
    created.push(n)
    x += NODE_W + 60
  }

  nodes.value = created
  // 分镜 → 角色/场景 引用连线
  const charNodes = created.filter((n) => n.node_type === 'character')
  const sceneNodes = created.filter((n) => n.node_type === 'scene')
  const shotNodes = created.filter((n) => n.node_type === 'shot')
  const newEdges: CanvasEdge[] = []
  for (const shNode of shotNodes) {
    const sh = shots.find((s) => s.id === shNode.ref_id)
    if (!sh) continue
    for (const cid of sh.character_ids || []) {
      const cn = charNodes.find((n) => n.ref_id === cid)
      if (cn) newEdges.push(await canvasApi.createEdge(projectId, { source_id: cn.id, target_id: shNode.id, edge_type: 'reference' }))
    }
    if (sh.scene_id) {
      const sn = sceneNodes.find((n) => n.ref_id === sh.scene_id)
      if (sn) newEdges.push(await canvasApi.createEdge(projectId, { source_id: sn.id, target_id: shNode.id, edge_type: 'reference' }))
    }
  }
  edges.value = newEdges
}

// ============ AI 自动策划 ============
const aiPlan = async () => {
  if (!project.value) return
  // 优先用「最新一版剧本的完整正文」作为 prompt（用户已经在画布里编辑过剧本的情况）
  let prompt = ''
  if (scriptVersions.items.length) {
    prompt = scriptVersions.items[0].content || scriptVersions.items[0].raw_text || ''
  }
  if (!prompt) prompt = project.value.prompt || ''
  if (!prompt) {
    ElMessage.warning('该项目没有创意描述，也没有保存的剧本。请先在「剧本」抽屉里编辑剧本或回首页填写。')
    return
  }
  planning.value = true
  try {
    await projectsApi.startCreation(projectId, {
      prompt,
      art_style: project.value.art_style || '',
      skill_code: 'drama_story',
    })
    ElMessage.success('AI 策划完成，正在生成画布节点')
    await loadAll()
    await loadScriptVersions()
    fitView()
  } catch {
    ElMessage.error('AI 策划失败')
  } finally {
    planning.value = false
  }
}

// ============ 批量操作 ============
const onBatchCommand = async (cmd: string) => {
  try {
    if (cmd === 'images') {
      await projectsApi.batchImages(projectId)
      ElMessage.success('已提交批量分镜图生成任务')
    } else if (cmd === 'videos') {
      await projectsApi.batchVideos(projectId)
      ElMessage.success('已提交批量分镜视频生成任务')
    } else if (cmd === 'compose') {
      const res = await projectsApi.compose(projectId)
      ElMessage.success(res.video_url ? '合成完成' : '合成任务已提交')
    }
    pollTasks()
  } catch {
    /* 错误已由拦截器提示 */
  }
}

// ============ 自动布局 ============
const autoLayout = async () => {
  const order = ['script', 'character', 'scene', 'prop', 'shot', 'storyboard', 'video', 'audio_separator', 'generation']
  const rows = new Map<string, CanvasNode[]>()
  for (const n of nodes.value) {
    if (!rows.has(n.node_type)) rows.set(n.node_type, [])
    rows.get(n.node_type)!.push(n)
  }
  let y = 0
  for (const type of order) {
    const list = rows.get(type)
    if (!list?.length) continue
    list.sort((a, b) => a.id - b.id)
    let x = 0
    for (const n of list) {
      n.position_x = x
      n.position_y = y
      await canvasApi.updateNode(n.id, { position_x: x, position_y: y })
      x += NODE_W + 60
    }
    y += NODE_H + 90
  }
  fitView()
}

// ============ 视图变换 ============
const onWheel = (e: WheelEvent) => {
  const factor = Math.exp(-e.deltaY * 0.0012)
  const next = Math.min(2.5, Math.max(0.2, scale.value * factor))
  const rect = viewportRef.value!.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  // 以鼠标为中心缩放
  pan.x = mx - ((mx - pan.x) / scale.value) * next
  pan.y = my - ((my - pan.y) / scale.value) * next
  scale.value = next
}

const zoomBy = (delta: number) => {
  const next = Math.min(2.5, Math.max(0.2, scale.value + delta))
  const rect = viewportRef.value?.getBoundingClientRect()
  const cx = rect ? rect.width / 2 : 400
  const cy = rect ? rect.height / 2 : 300
  pan.x = cx - ((cx - pan.x) / scale.value) * next
  pan.y = cy - ((cy - pan.y) / scale.value) * next
  scale.value = next
}

const fitView = () => {
  if (!nodes.value.length || !viewportRef.value) return
  const minX = Math.min(...nodes.value.map((n) => n.position_x))
  const minY = Math.min(...nodes.value.map((n) => n.position_y))
  const maxX = Math.max(...nodes.value.map((n) => n.position_x + NODE_W))
  const maxY = Math.max(...nodes.value.map((n) => n.position_y + NODE_H))
  const rect = viewportRef.value.getBoundingClientRect()
  const s = Math.min(
    (rect.width - 120) / (maxX - minX),
    (rect.height - 120) / (maxY - minY),
    1,
  )
  scale.value = Math.max(0.2, s)
  pan.x = (rect.width - (maxX - minX) * scale.value) / 2 - minX * scale.value
  pan.y = (rect.height - (maxY - minY) * scale.value) / 2 - minY * scale.value
}

// 平移
const panState = { active: false, sx: 0, sy: 0, ox: 0, oy: 0 }
const onPanStart = (e: MouseEvent) => {
  panState.active = true
  panState.sx = e.clientX
  panState.sy = e.clientY
  panState.ox = pan.x
  panState.oy = pan.y
  window.addEventListener('mousemove', onPanMove)
  window.addEventListener('mouseup', onPanEnd)
}
const onPanMove = (e: MouseEvent) => {
  if (!panState.active) return
  pan.x = panState.ox + (e.clientX - panState.sx)
  pan.y = panState.oy + (e.clientY - panState.sy)
}
const onPanEnd = () => {
  panState.active = false
  window.removeEventListener('mousemove', onPanMove)
  window.removeEventListener('mouseup', onPanEnd)
}
// 点击空白（几乎无拖动）→ 取消选中
const onViewportClick = () => {
  const moved = Math.abs(pan.x - panState.ox) + Math.abs(pan.y - panState.oy)
  if (moved < 4) selectedId.value = null
}

// 节点拖拽
const dragState = { node: null as CanvasNode | null, sx: 0, sy: 0, ox: 0, oy: 0 }
const onNodeDragStart = (e: MouseEvent, n: CanvasNode) => {
  dragState.node = n
  dragState.sx = e.clientX
  dragState.sy = e.clientY
  dragState.ox = n.position_x
  dragState.oy = n.position_y
  window.addEventListener('mousemove', onNodeDragMove)
  window.addEventListener('mouseup', onNodeDragEnd)
}
const onNodeDragMove = (e: MouseEvent) => {
  const n = dragState.node
  if (!n) return
  n.position_x = dragState.ox + (e.clientX - dragState.sx) / scale.value
  n.position_y = dragState.oy + (e.clientY - dragState.sy) / scale.value
}
const onNodeDragEnd = async () => {
  const n = dragState.node
  window.removeEventListener('mousemove', onNodeDragMove)
  window.removeEventListener('mouseup', onNodeDragEnd)
  dragState.node = null
  if (n) {
    await canvasApi.updateNode(n.id, { position_x: Math.round(n.position_x), position_y: Math.round(n.position_y) }).catch(() => {})
  }
}

// ============ 连线几何 ============
// 智能锚点：根据两节点相对位置选择 上/下/左/右 边缘中点连接，避免线穿过卡片
const anchorPoints = (s: CanvasNode, t: CanvasNode) => {
  const sc = { x: s.position_x + NODE_W / 2, y: s.position_y + NODE_H / 2 }
  const tc = { x: t.position_x + NODE_W / 2, y: t.position_y + NODE_H / 2 }
  const dx = tc.x - sc.x
  const dy = tc.y - sc.y
  if (Math.abs(dx) >= Math.abs(dy)) {
    const sgn = dx >= 0 ? 1 : -1
    return {
      p1: { x: sc.x + (sgn * NODE_W) / 2, y: sc.y },
      p2: { x: tc.x - (sgn * NODE_W) / 2, y: tc.y },
      dir: 'h' as const,
    }
  }
  const sgn = dy >= 0 ? 1 : -1
  return {
    p1: { x: sc.x, y: sc.y + (sgn * NODE_H) / 2 },
    p2: { x: tc.x, y: tc.y - (sgn * NODE_H) / 2 },
    dir: 'v' as const,
  }
}

// 三次贝塞尔路径 + 中点（用于放标签）
const bezier = (p1: { x: number; y: number }, p2: { x: number; y: number }, dir: 'h' | 'v', bow = 0) => {
  const dist = Math.hypot(p2.x - p1.x, p2.y - p1.y)
  const k = Math.max(48, dist * 0.38)
  let c1, c2
  if (dir === 'h') {
    const sgn = p2.x >= p1.x ? 1 : -1
    c1 = { x: p1.x + sgn * k, y: p1.y + bow }
    c2 = { x: p2.x - sgn * k, y: p2.y + bow }
  } else {
    const sgn = p2.y >= p1.y ? 1 : -1
    c1 = { x: p1.x + bow, y: p1.y + sgn * k }
    c2 = { x: p2.x + bow, y: p2.y - sgn * k }
  }
  const d = `M ${p1.x} ${p1.y} C ${c1.x} ${c1.y}, ${c2.x} ${c2.y}, ${p2.x} ${p2.y}`
  // t=0.5 处的贝塞尔点
  const mid = {
    x: (p1.x + 3 * c1.x + 3 * c2.x + p2.x) / 8,
    y: (p1.y + 3 * c1.y + 3 * c2.y + p2.y) / 8,
  }
  return { d, mid }
}

// 引用边（分镜 ← 角色/场景）
const refEdgeGeoms = computed(() => {
  const byId = new Map(nodes.value.map((n) => [n.id, n]))
  return edges.value
    .filter((e) => e.edge_type !== 'relation')
    .map((e) => {
      const s = byId.get(e.source_id)
      const t = byId.get(e.target_id)
      if (!s || !t) return null
      const { p1, p2, dir } = anchorPoints(s, t)
      const { d } = bezier(p1, p2, dir)
      const key = `e${e.id}`
      const active = hoverEdgeKey.value === key || selectedId.value === e.source_id || selectedId.value === e.target_id
      const dim = selectedId.value !== null && !active
      return { key, d, active, dim }
    })
    .filter(Boolean) as { key: string; d: string; active: boolean; dim: boolean }[]
})

// 关系类型 → 配色
const RELATION_COLORS: Record<string, string> = {
  恋人: '#f472b6', 暗恋: '#f9a8d4', 夫妻: '#fb7185',
  亲子: '#fb923c', 兄弟姐妹: '#fbbf24',
  朋友: '#34d399', 同事: '#60a5fa', 师生: '#818cf8',
  对手: '#ef4444', 仇人: '#dc2626', 陌生人: '#94a3b8',
}
const relationColor = (t: string) => RELATION_COLORS[t] || '#2de0c8'
const withAlpha = (hex: string, a: number) => {
  const r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${a})`
}

// 角色关系边（角色节点之间，实线+弧形+标签）
const relEdgeGeoms = computed(() => {
  const charNodes = nodes.value.filter((n) => n.node_type === 'character')
  const byRef = new Map(charNodes.map((n) => [n.ref_id, n]))
  // 检测双向关系对 → 用相反方向的弧线分开，避免两条线重叠
  const pairCount = new Map<string, number>()
  for (const r of relations.value) {
    const k = [r.from_character_id, r.to_character_id].sort((a, b) => a - b).join('-')
    pairCount.set(k, (pairCount.get(k) || 0) + 1)
  }
  return relations.value
    .map((r) => {
      const s = byRef.get(r.from_character_id)
      const t = byRef.get(r.to_character_id)
      if (!s || !t) return null
      const { p1, p2, dir } = anchorPoints(s, t)
      const pairKey = [r.from_character_id, r.to_character_id].sort((a, b) => a - b).join('-')
      const bidir = (pairCount.get(pairKey) || 0) > 1
      // 弧线偏移：单向小幅上拱；双向按 from<to 分上/下
      const bow = bidir ? (r.from_character_id < r.to_character_id ? -52 : 52) : -30
      const { d, mid } = bezier(p1, p2, dir, bow)
      const color = relationColor(r.relation_type)
      const key = `r${r.id}`
      const active = hoverEdgeKey.value === key || selectedId.value === s.id || selectedId.value === t.id
      const dim = selectedId.value !== null && !active
      const label = r.relation_type
      return {
        key, d, active, dim, color,
        colorDim: withAlpha(color, 0.35),
        label, labelW: label.length * 11 + 14,
        labelX: mid.x, labelY: mid.y,
      }
    })
    .filter(Boolean) as { key: string; d: string; active: boolean; dim: boolean; color: string; colorDim: string; label: string; labelW: number; labelX: number; labelY: number }[]
})

// ============ 节点工具箱 ============
const NODE_TYPE_COLORS: Record<string, string> = {
  script: '#94a3b8', character: '#f472b6', scene: '#34d399', prop: '#fbbf24',
  shot: '#2de0c8', storyboard: '#60a5fa', video: '#a78bfa',
  generation: '#fb923c', audio_separator: '#22d3ee',
}
const nodeTypeColor = (t: string) => NODE_TYPE_COLORS[t] || '#2de0c8'

// 选中节点时，与其无直接连线的节点淡化，突出关联关系
const dimmedNodes = computed(() => {
  const sel = selectedId.value
  if (sel === null) return new Set<number>()
  const linked = new Set<number>([sel])
  for (const e of edges.value) {
    if (e.source_id === sel) linked.add(e.target_id)
    if (e.target_id === sel) linked.add(e.source_id)
  }
  // 关系边也纳入关联
  const charByRef = new Map(nodes.value.filter((n) => n.node_type === 'character').map((n) => [n.ref_id, n.id]))
  const selNode = nodes.value.find((n) => n.id === sel)
  for (const r of relations.value) {
    const a = charByRef.get(r.from_character_id)
    const b = charByRef.get(r.to_character_id)
    if (a && b && (a === sel || b === sel)) { linked.add(a); linked.add(b) }
  }
  if (selNode?.node_type === 'character' && selNode.ref_id) {
    for (const r of relations.value) {
      if (r.from_character_id === selNode.ref_id || r.to_character_id === selNode.ref_id) {
        const a = charByRef.get(r.from_character_id)
        const b = charByRef.get(r.to_character_id)
        if (a) linked.add(a)
        if (b) linked.add(b)
      }
    }
  }
  return new Set(nodes.value.filter((n) => !linked.has(n.id)).map((n) => n.id))
})

const nodeTypeLabel = (t: string) =>
  ({
    script: '剧本', character: '角色', scene: '场景', prop: '道具',
    shot: '分镜图', storyboard: '分镜', video: '视频',
    generation: '生成', audio_separator: '音频',
  }[t] || t)

const nodeIcon = (t: string) =>
  ({
    character: User, scene: Place, shot: Film, storyboard: Film,
    video: VideoPlay, script: Document, audio_separator: Headset,
  }[t] || Film)

const nodeActions = (n: CanvasNode) => {
  if (n.node_type === 'shot' || n.node_type === 'storyboard') {
    const acts: { cmd: string; label: string }[] = []
    if (nodeVideoUrl(n)) acts.push({ cmd: 'preview-video', label: '▶ 预览生成的视频' })
    acts.push(
      { cmd: 'design', label: '设计分镜（生图/AI优化）' },
      { cmd: 'video', label: '视频生成' },
      { cmd: 'grid9', label: '九宫格' },
      { cmd: 'extend', label: '剧情推演' },
      { cmd: 'audio-separate', label: '音频分离' },
      { cmd: 'lipsync', label: '对口型' },
      { cmd: 'tts', label: 'TTS 配音' },
    )
    return acts
  }
  if (n.node_type === 'scene') {
    return [
      { cmd: 'design', label: '设计场景（生图/AI优化）' },
      { cmd: 'panorama', label: '720° 全景' },
    ]
  }
  if (n.node_type === 'character') {
    return [
      { cmd: 'design', label: '设计角色（多视图/AI优化）' },
    ]
  }
  if (n.node_type === 'script') {
    return [
      { cmd: 'design', label: '剧本优化 / 角色关系' },
    ]
  }
  if (n.node_type === 'video') {
    return [
      { cmd: 'audio-separate', label: '音频分离' },
      { cmd: 'lipsync', label: '对口型' },
      { cmd: 'audio-translate', label: '音频翻译(出海)' },
    ]
  }
  return []
}

const videoDialog = reactive({ visible: false, model: 'seedance-2.0', node: null as CanvasNode | null, title: '', busy: false })

// ============ 视频预览（本地已下载视频，支持全屏） ============
const videoPreviewRef = ref<HTMLVideoElement | null>(null)
const videoPreview = reactive({
  visible: false,
  url: '',
  title: '',
  isFullscreen: false,
})

// 取节点已生成的视频地址（优先 meta.video_url，回退到分镜实体 video_url）
const nodeVideoUrl = (n: CanvasNode): string => {
  const fromMeta = (n.meta && (n.meta as any).video_url) || ''
  if (fromMeta) return fromMeta
  // video 类型节点用缩略图/输出地址
  if (n.node_type === 'video') return (n.meta && (n.meta as any).output_url) || ''
  return ''
}

const openVideoPreview = (n: CanvasNode) => {
  const url = nodeVideoUrl(n)
  if (!url) {
    ElMessage.warning('该节点暂无已生成的视频')
    return
  }
  videoPreview.url = url
  videoPreview.title = n.title || '分镜视频'
  videoPreview.visible = true
}

// 从设计面板打开分镜视频预览（全屏弹窗）
const openShotVideoPreview = (sh: Shot) => {
  if (!sh?.video_url) {
    ElMessage.warning('该分镜暂无已生成的视频')
    return
  }
  videoPreview.url = sh.video_url
  videoPreview.title = `${sh.shot_code || 'SC' + sh.shot_no} 分镜视频`
  videoPreview.visible = true
}

const onVideoPreviewClosed = () => {
  // 退出全屏并停止播放
  if (document.fullscreenElement) document.exitFullscreen().catch(() => {})
  videoPreview.isFullscreen = false
  videoPreview.url = ''
}

const toggleFullscreen = async () => {
  const wrap = document.getElementById('cv-video-wrap')
  const v = videoPreviewRef.value
  const target = wrap || v
  if (!target) return
  try {
    if (!document.fullscreenElement) {
      await target.requestFullscreen()
      // 全屏后让 video 撑满
      if (v) { v.style.maxHeight = '100vh'; v.style.height = '100vh'; v.style.width = '100vw'; v.style.objectFit = 'contain' }
      videoPreview.isFullscreen = true
    } else {
      await document.exitFullscreen()
    }
  } catch {
    ElMessage.warning('当前浏览器不支持全屏')
  }
}

// 监听全屏变化，退出全屏时恢复样式
const onFullscreenChange = () => {
  if (!document.fullscreenElement) {
    videoPreview.isFullscreen = false
    const v = videoPreviewRef.value
    if (v) { v.style.maxHeight = '60vh'; v.style.height = ''; v.style.width = ''; v.style.objectFit = '' }
  }
}

// 自动播放：浏览器策略拦截带声音自动播放时，回退静音播放（用户可手动开声音）
const tryAutoPlay = async () => {
  const v = videoPreviewRef.value
  if (!v) return
  try {
    await v.play()
  } catch {
    try {
      v.muted = true
      await v.play()
    } catch { /* 用户手动点播放 */ }
  }
}

const onNodeCommand = async (cmd: string, n: CanvasNode) => {
  if (cmd === 'preview-video') {
    openVideoPreview(n)
    return
  }
  if (cmd === '__delete') {
    await canvasApi.deleteNode(n.id)
    nodes.value = nodes.value.filter((x) => x.id !== n.id)
    edges.value = edges.value.filter((e) => e.source_id !== n.id && e.target_id !== n.id)
    return
  }
  if (cmd === 'design') {
    await openDesignPanel(n)
    return
  }
  if (cmd === 'video') {
    videoDialog.node = n
    videoDialog.title = n.title
    videoDialog.visible = true
    return
  }
  if (cmd === 'grid9') {
    if (!n.ref_id) return
    n.status = 'running'
    const res = await mediaApi.grid9(n.ref_id, { prompt: n.title }).catch(() => null)
    n.status = ''
    if (res?.images?.length) ElMessage.success('九宫格已生成（见任务结果）')
    return
  }
  if (cmd === 'extend') {
    if (!n.ref_id) return
    n.status = 'running'
    await mediaApi.extend(n.ref_id, { direction: 'after', seconds: 3 }).catch(() => {})
    n.status = ''
    ElMessage.success('剧情推演完成')
    return
  }
  if (cmd === 'audio-separate') {
    if (!n.ref_id) return
    n.status = 'running'
    await mediaApi.audioSeparate(n.ref_id).catch(() => {})
    n.status = ''
    ElMessage.success('音频分离完成')
    return
  }
  if (cmd === 'lipsync') {
    if (!n.ref_id) return
    n.status = 'running'
    await mediaApi.lipsync(n.ref_id).catch(() => {})
    n.status = ''
    ElMessage.success('口型同步完成')
    return
  }
  if (cmd === 'tts') {
    if (!n.ref_id) return
    n.status = 'running'
    await mediaApi.tts(n.ref_id, { text: n.title }).catch(() => {})
    n.status = ''
    ElMessage.success('TTS 配音完成')
    return
  }
  if (cmd === 'audio-translate') {
    if (!n.ref_id) return
    n.status = 'running'
    await mediaApi.audioTranslate(n.ref_id, { target_language: 'en' }).catch(() => {})
    n.status = ''
    ElMessage.success('音频翻译完成')
    return
  }
  if (cmd === 'panorama') {
    if (!n.ref_id) return
    n.status = 'running'
    const res = await mediaApi.panorama(n.ref_id).catch(() => null)
    n.status = ''
    if (res?.panorama_url) {
      n.thumbnail_url = res.panorama_url
      await canvasApi.updateNode(n.id, { thumbnail_url: res.panorama_url }).catch(() => {})
    }
    return
  }
}

// ============ 节点设计面板 ============
const CHAR_VIEWS = [
  { key: 'closeup', label: '面部特写' },
  { key: 'front', label: '正面全身' },
  { key: 'side', label: '侧面' },
  { key: 'back', label: '背面' },
  { key: 'expression', label: '表情组' },
]
const RELATION_TYPES = ['恋人', '夫妻', '亲子', '兄弟姐妹', '朋友', '同事', '师生', '对手', '仇人', '暗恋', '陌生人']

const designPanel = reactive({
  visible: false,
  busy: false,
  type: '' as '' | 'character' | 'scene' | 'shot' | 'script',
  title: '',
  node: null as CanvasNode | null,
  character: null as Character | null,
  scene: null as Scene | null,
  shot: null as Shot | null,
  requirement: '',
})
const relations = ref<CharacterRelation[]>([])
const charOptions = ref<Character[]>([])
const newRelation = reactive({ from: null as number | null, to: null as number | null, type: '恋人' })

const openDesignPanel = async (n: CanvasNode) => {
  designPanel.node = n
  designPanel.requirement = ''
  designPanel.character = null
  designPanel.scene = null
  designPanel.shot = null

  if (n.node_type === 'character' && n.ref_id) {
    const chars = await assetsApi.characters(projectId)
    designPanel.character = chars.find((c) => c.id === n.ref_id) || null
    designPanel.title = `角色设计 · ${n.title}`
    designPanel.type = 'character'
  } else if (n.node_type === 'scene' && n.ref_id) {
    const scenes = await assetsApi.scenes(projectId)
    designPanel.scene = scenes.find((s) => s.id === n.ref_id) || null
    designPanel.title = `场景设计 · ${n.title}`
    designPanel.type = 'scene'
  } else if ((n.node_type === 'shot' || n.node_type === 'storyboard') && n.ref_id) {
    const shots = await assetsApi.shots(projectId)
    designPanel.shot = shots.find((s) => s.id === n.ref_id) || null
    designPanel.title = `分镜设计 · ${n.title}`
    designPanel.type = 'shot'
  } else if (n.node_type === 'script') {
    designPanel.title = '剧本优化 · 角色关系'
    designPanel.type = 'script'
    charOptions.value = await assetsApi.characters(projectId)
    relations.value = await designApi.listRelations(projectId).catch(() => [])
  } else {
    ElMessage.info('该节点类型暂不支持设计面板')
    return
  }
  designPanel.visible = true
}

// 双击节点也打开设计面板
const onNodeDblClick = (n: CanvasNode) => {
  if (['character', 'scene', 'shot', 'storyboard', 'script'].includes(n.node_type)) openDesignPanel(n)
}

// 顶栏入口：打开剧本优化 / 角色关系面板（无需 script 节点）
const openScriptPanel = async () => {
  designPanel.node = null
  designPanel.requirement = ''
  designPanel.character = null
  designPanel.scene = null
  designPanel.shot = null
  designPanel.title = '剧本优化 · 角色关系'
  designPanel.type = 'script'
  charOptions.value = await assetsApi.characters(projectId)
  relations.value = await designApi.listRelations(projectId).catch(() => [])
  await loadScriptVersions()
  designPanel.visible = true
}

// 加载项目下的全部剧本版本（持久化的剧本实体）
const scriptVersions = reactive<{ items: ScriptVersion[]; total: number; current_version: number; loading: boolean }>({
  items: [], total: 0, current_version: 0, loading: false,
})
const loadScriptVersions = async () => {
  scriptVersions.loading = true
  try {
    const res = await scriptsApi.list(projectId)
    scriptVersions.items = res.items
    scriptVersions.total = res.total
    scriptVersions.current_version = res.current_version
  } catch {
    scriptVersions.items = []
    scriptVersions.total = 0
  } finally {
    scriptVersions.loading = false
  }
}
const formatScriptDate = (iso: string) => {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const syncNodeThumb = (url: string) => {
  const n = designPanel.node
  if (n && url) {
    n.thumbnail_url = url
    canvasApi.updateNode(n.id, { thumbnail_url: url }).catch(() => {})
  }
}

const genDesignSheet = async () => {
  const ch = designPanel.character
  if (!ch) return
  designPanel.busy = true
  try {
    const res = await designApi.designSheet(ch.id, 'closeup,front,side,expression')
    if (res?.view_images) {
      ch.view_images = res.view_images
      ch.portrait_url = res.portrait_url
      syncNodeThumb(res.portrait_url)
      ElMessage.success('角色设计稿已生成')
    }
  } catch { /* 拦截器已提示 */ } finally {
    designPanel.busy = false
  }
}

const regenView = async (view: string) => {
  const ch = designPanel.character
  if (!ch) return
  designPanel.busy = true
  try {
    const res = await designApi.generateView(ch.id, view)
    if (res?.url) {
      ch.view_images = { ...(ch.view_images || {}), [view]: res.url }
      if (res.portrait_url) {
        ch.portrait_url = res.portrait_url
        syncNodeThumb(res.portrait_url)
      }
      ElMessage.success('视图已更新')
    }
  } catch { /* ignore */ } finally {
    designPanel.busy = false
  }
}

const saveCharacter = async () => {
  const ch = designPanel.character
  if (!ch) return
  designPanel.busy = true
  try {
    await assetsApi.updateCharacter(ch.id, {
      name: ch.name, alias: ch.alias, age: ch.age, gender: ch.gender, role: ch.role,
      appearance: ch.appearance, outfit: ch.outfit, personality: ch.personality, backstory: ch.backstory,
    })
    ElMessage.success('角色设定已保存')
  } catch { /* ignore */ } finally {
    designPanel.busy = false
  }
}

const saveScene = async () => {
  const sc = designPanel.scene
  if (!sc) return
  designPanel.busy = true
  try {
    await assetsApi.updateScene(sc.id, {
      name: sc.name, location: sc.location, time_of_day: sc.time_of_day,
      weather: sc.weather, mood: sc.mood, description: sc.description, visual_prompt: sc.visual_prompt,
    })
    ElMessage.success('场景设定已保存')
  } catch { /* ignore */ } finally {
    designPanel.busy = false
  }
}

const saveShot = async () => {
  const sh = designPanel.shot
  if (!sh) return
  designPanel.busy = true
  try {
    await assetsApi.updateShot(sh.id, {
      description: sh.description, composition: sh.composition,
      camera_movement: sh.camera_movement, camera_angle: sh.camera_angle,
      dialogue: sh.dialogue, duration_sec: sh.duration_sec,
    })
    ElMessage.success('镜头设定已保存')
  } catch { /* ignore */ } finally {
    designPanel.busy = false
  }
}

const genSceneImage = async () => {
  const sc = designPanel.scene
  if (!sc) return
  designPanel.busy = true
  try {
    const res = await designApi.generateSceneImage(sc.id)
    if (res?.panorama_url) {
      sc.panorama_url = res.panorama_url
      syncNodeThumb(res.panorama_url)
      ElMessage.success('场景图已生成')
    }
  } catch { /* ignore */ } finally {
    designPanel.busy = false
  }
}

const genShotImage = async () => {
  const sh = designPanel.shot
  if (!sh) return
  designPanel.busy = true
  try {
    const res = await designApi.generateShotImage(sh.id)
    if (res?.image_url) {
      sh.image_url = res.image_url
      syncNodeThumb(res.image_url)
      ElMessage.success('分镜图已生成')
    }
  } catch { /* ignore */ } finally {
    designPanel.busy = false
  }
}

const optimizeEntity = async () => {
  const req = designPanel.requirement.trim()
  if (!req) return
  designPanel.busy = true
  try {
    if (designPanel.type === 'character' && designPanel.character) {
      const res = await designApi.optimizeCharacter(designPanel.character.id, req)
      Object.assign(designPanel.character, res.character)
      ElMessage.success('角色设定已 AI 优化，可重新生成设计稿')
    } else if (designPanel.type === 'scene' && designPanel.scene) {
      const res = await designApi.optimizeScene(designPanel.scene.id, req)
      Object.assign(designPanel.scene, res.scene)
      ElMessage.success('场景设定已 AI 优化')
    } else if (designPanel.type === 'shot' && designPanel.shot) {
      const res = await designApi.optimizeShot(designPanel.shot.id, req)
      Object.assign(designPanel.shot, res.shot)
      ElMessage.success('分镜已 AI 优化')
    }
    designPanel.requirement = ''
  } catch { /* ignore */ } finally {
    designPanel.busy = false
  }
}

const optimizeScript = async () => {
  const req = designPanel.requirement.trim()
  if (!req) return
  designPanel.busy = true
  try {
    const res = await designApi.optimizeScript(projectId, req)
    ElMessage.success(`剧本已优化（新版本 v${res.version}），画布节点已同步`)
    designPanel.requirement = ''
    await loadAll()
    await loadScriptVersions()
  } catch { /* ignore */ } finally {
    designPanel.busy = false
  }
}

// ============ 剧本版本编辑 ============
// 用户编辑某个剧本版本 → 保存（仍保留旧版本，只是改这一版的文本）
const editingScriptId = ref<number | null>(null)
const editingScript = reactive<{ title: string; logline: string; content: string }>({
  title: '', logline: '', content: '',
})
const scriptSaving = ref(false)

const startEditScript = (sv: ScriptVersion) => {
  editingScriptId.value = sv.id
  editingScript.title = sv.title || ''
  editingScript.logline = sv.logline || ''
  editingScript.content = sv.content || ''
}

const cancelEditScript = () => {
  editingScriptId.value = null
}

const saveEditScript = async (scriptId: number) => {
  if (!editingScript.title.trim() || !editingScript.content.trim()) {
    ElMessage.warning('剧名和剧本正文不能为空')
    return
  }
  scriptSaving.value = true
  try {
    await scriptsApi.update(scriptId, {
      title: editingScript.title.trim(),
      logline: editingScript.logline.trim(),
      content: editingScript.content,
    })
    ElMessage.success('剧本已保存（同一版本号内编辑，旧版本快照保留在系统）')
    editingScriptId.value = null
    await loadScriptVersions()
  } catch { /* ignore */ } finally {
    scriptSaving.value = false
  }
}

// ============ 把指定剧本版本重新应用到画布 ============
const applyingScriptId = ref<number | null>(null)
const applyScript = async (scriptId: number) => {
  try {
    await ElMessageBox.confirm(
      '将基于此剧本版本重新解析角色 / 场景 / 分镜并重建画布节点，当前画布实体将被覆盖（已生成的图片 / 视频不受影响，可重新批量生成）。',
      '重新应用到画布',
      { type: 'warning' },
    )
  } catch { return }
  applyingScriptId.value = scriptId
  try {
    const res = await scriptsApi.applyToCanvas(scriptId)
    ElMessage.success(
      `已应用剧本到画布：${res.character_count} 角色 / ${res.scene_count} 场景 / ${res.shot_count} 分镜 / ${res.canvas_node_count} 画布节点`,
    )
    await loadAll()
    fitView()
  } catch { /* ignore */ } finally {
    applyingScriptId.value = null
  }
}

const autoRelations = async () => {
  designPanel.busy = true
  try {
    const res = await designApi.autoGenerateRelations(projectId)
    ElMessage.success(`AI 已设计 ${res.count} 条角色关系`)
    relations.value = await designApi.listRelations(projectId).catch(() => [])
  } catch { /* ignore */ } finally {
    designPanel.busy = false
  }
}

const addRelation = async () => {
  if (!newRelation.from || !newRelation.to || newRelation.from === newRelation.to) {
    ElMessage.warning('请选择两个不同的角色')
    return
  }
  try {
    await designApi.createRelation(projectId, {
      from_character_id: newRelation.from,
      to_character_id: newRelation.to,
      relation_type: newRelation.type,
    })
    relations.value = await designApi.listRelations(projectId)
    newRelation.from = null
    newRelation.to = null
  } catch { /* ignore */ }
}

const removeRelation = async (rid: number) => {
  try {
    await designApi.deleteRelation(rid)
    relations.value = relations.value.filter((r) => r.id !== rid)
  } catch { /* ignore */ }
}

const confirmVideoGen = async () => {
  const n = videoDialog.node
  if (!n?.ref_id) return
  videoDialog.busy = true
  try {
    await tasksApi.generateVideo(projectId, {
      prompt: n.title,
      image_url: n.thumbnail_url,
      shot_id: n.ref_id,
    })
    ElMessage.success('视频生成任务已提交')
    videoDialog.visible = false
    pollTasks()
  } finally {
    videoDialog.busy = false
  }
}

// ============ 任务轮询（渐进刷新：每轮都同步缩略图/状态，生成一个显示一个） ============
let pollTimer: ReturnType<typeof setInterval> | null = null
let lastDoneCount = 0
const pollTasks = async () => {
  try {
    const [list, snap] = await Promise.all([
      tasksApi.list({ project_id: projectId, limit: 50 }),
      canvasApi.snapshot(projectId),
    ])
    const running = list.filter((t) => ['pending', 'running'].includes(t.status)).length
    const done = list.filter((t) => t.status === 'success').length
    runningTasks.value = running

    // 增量同步远端节点（缩略图/状态/视频地址），保留本地位置
    const remoteById = new Map(snap.nodes.map((r) => [r.id, r]))
    let changed = false
    for (const n of nodes.value) {
      const r = remoteById.get(n.id)
      if (!r) continue
      if (r.thumbnail_url && r.thumbnail_url !== n.thumbnail_url) { n.thumbnail_url = r.thumbnail_url; changed = true }
      if (r.status !== n.status) { n.status = r.status; changed = true }
      // 同步 meta（含 video_url）：视频生成完成后节点变为可预览
      const rv = (r.meta && (r.meta as any).video_url) || ''
      const nv = (n.meta && (n.meta as any).video_url) || ''
      if (rv && rv !== nv) { n.meta = { ...(n.meta || {}), ...r.meta }; changed = true }
    }
    // 有新完成的任务 → 提示一次
    if (done > lastDoneCount && lastDoneCount > 0) {
      ElMessage.success(`又有 ${done - lastDoneCount} 个生成任务完成`)
    }
    lastDoneCount = done
    // 全部完成时刷新项目统计
    if (running === 0 && changed && project.value) {
      project.value = await projectsApi.get(projectId)
    }
  } catch {
    /* ignore */
  }
}

onMounted(async () => {
  try {
    await loadAll()
    videoModels.value = (await modelsApi.list({ model_type: 'video' }))
    if (nodes.value.length) fitView()
    pollTasks()
    pollTimer = setInterval(pollTasks, 4000)
    document.addEventListener('fullscreenchange', onFullscreenChange)
  } catch {
    ElMessage.error('项目加载失败')
    router.push('/projects')
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
  document.removeEventListener('fullscreenchange', onFullscreenChange)
})
</script>
