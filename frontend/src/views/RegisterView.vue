<template>
  <div class="min-h-screen bg-ink-950 text-slate-100 flex items-center justify-center dot-grid px-4">
    <div class="w-full max-w-md">
      <!-- 顶部品牌 -->
      <div class="flex items-center justify-center gap-3 mb-8">
        <div class="w-12 h-12 rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center shadow-glow-brand">
          <span class="text-black font-black text-2xl">L</span>
        </div>
        <div class="flex flex-col">
          <span class="text-2xl font-black tracking-tight">LBP_M</span>
          <span class="text-xs text-slate-500">AI 短剧创作平台 · 致敬卢米埃尔兄弟</span>
        </div>
      </div>

      <div class="lbp-card p-8 shadow-card">
        <h1 class="text-xl font-semibold mb-1">创建账号</h1>
        <p class="text-sm text-slate-500 mb-6">
          <span class="text-brand-400">首位注册的用户将自动成为管理员</span>
        </p>

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent>
          <el-form-item label="昵称" prop="display_name">
            <el-input
              v-model="form.display_name"
              placeholder="想在 LBP_M 上展示的名字"
              size="large"
              :prefix-icon="User"
              maxlength="32"
              show-word-limit
            />
          </el-form-item>

          <el-form-item label="邮箱" prop="email">
            <el-input
              v-model="form.email"
              type="email"
              placeholder="your@email.com"
              autocomplete="email"
              size="large"
              :prefix-icon="Message"
            />
          </el-form-item>

          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="至少 6 位"
              autocomplete="new-password"
              size="large"
              show-password
              :prefix-icon="Lock"
            />
          </el-form-item>

          <el-form-item label="确认密码" prop="password_confirm">
            <el-input
              v-model="form.password_confirm"
              type="password"
              placeholder="再输入一次"
              autocomplete="new-password"
              size="large"
              show-password
              :prefix-icon="Lock"
              @keyup.enter="handleSubmit"
            />
          </el-form-item>

          <el-button
            type="primary"
            size="large"
            class="w-full mt-2"
            :loading="submitting"
            @click="handleSubmit"
          >
            {{ submitting ? '注册中...' : '创建账号' }}
          </el-button>
        </el-form>

        <div class="mt-6 text-center text-sm text-slate-500">
          已有账号？
          <router-link to="/login" class="text-brand-400 hover:text-brand-300">直接登录</router-link>
        </div>
      </div>

      <div class="mt-6 text-center text-xs text-slate-600">
        <router-link to="/explore" class="hover:text-slate-400">先逛逛首页</router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Message, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive({
  display_name: '',
  email: '',
  password: '',
  password_confirm: '',
})

// 自定义校验：两次密码一致
const validatePassword2 = (_rule: any, value: string, callback: (err?: Error) => void) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules: FormRules = {
  display_name: [
    { required: true, message: '请输入昵称', trigger: 'blur' },
    { min: 2, max: 32, message: '昵称长度 2-32 个字符', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 64, message: '密码长度 6-64 位', trigger: 'blur' },
  ],
  password_confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    { validator: validatePassword2, trigger: 'blur' },
  ],
}

async function handleSubmit() {
  if (!formRef.value) return
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  submitting.value = true
  try {
    await auth.register(form.email, form.password, form.display_name)
    ElMessage.success('注册成功，已自动登录')
    router.replace('/projects')
  } catch (e: any) {
    console.error('register failed', e)
  } finally {
    submitting.value = false
  }
}
</script>