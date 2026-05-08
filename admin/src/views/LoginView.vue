<template>
  <div class="min-h-screen bg-gray-100 flex flex-col items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
    <div class="max-w-md w-full space-y-8 flex-1 flex flex-col justify-center">
      <div>
        <h2 class="mt-6 text-center text-3xl font-extrabold text-gray-900">
          管理后台登录
        </h2>
        <p class="mt-2 text-center text-sm text-gray-600">
          请输入您的登录凭据
        </p>
      </div>
      <form class="mt-8 space-y-6" @submit.prevent="handleLogin">
        <div class="rounded-md shadow-sm -space-y-px">
          <div>
            <label for="username" class="sr-only">用户名</label>
            <input
              id="username"
              v-model="form.username"
              name="username"
              type="text"
              required
              class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-t-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
              placeholder="用户名"
            />
          </div>
          <div>
            <label for="password" class="sr-only">密码</label>
            <input
              id="password"
              v-model="form.password"
              name="password"
            type="password"
              required
              class="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 rounded-b-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 focus:z-10 sm:text-sm"
              placeholder="密码"
            />
          </div>
        </div>

        <div>
          <button
            type="submit"
            :disabled="loading"
            class="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50"
          >
            <span v-if="loading" class="absolute left-0 inset-y-0 flex items-center pl-3">
              <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </span>
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </div>

        <div
          v-if="error"
          role="alert"
          data-testid="login-error"
          class="text-red-600 text-center text-sm"
        >
          {{ error }}
        </div>
      </form>
    </div>
    
    <!-- ICP备案信息 -->
    <footer class="icp-footer">
      <div class="icp-container">
        <a href="https://beian.miit.gov.cn/" target="_blank" rel="noopener noreferrer">
          京ICP备18061239号-1
        </a>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const form = reactive({
  username: '',
  password: ''
})

const loading = ref(false)
const error = ref('')

const handleLogin = async () => {
  if (!form.username || !form.password) {
    error.value = '请输入用户名和密码'
    return
  }

  loading.value = true
  error.value = ''

  try {
    await authStore.login({
      username: form.username,
      password: form.password
    })
    
    // 登录成功，跳转到dashboard
    router.push('/dashboard')
  } catch (err) {
    error.value = err instanceof Error ? err.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgb(249 250 251);
  padding: 3rem 1rem;
}

@media (min-width: 640px) {
  .login-container {
    padding: 3rem 1.5rem;
  }
}

@media (min-width: 1024px) {
  .login-container {
    padding: 3rem 2rem;
  }
}

.login-card {
  max-width: 28rem;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 2rem;
  background-color: white;
  padding: 2rem;
  border-radius: 0.5rem;
  box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
}

.login-header {
  text-align: center;
}

.login-form {
  margin-top: 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.login-info {
  margin-top: 1.5rem;
  text-align: center;
}

/* ICP备案信息样式 */
.icp-footer {
  background: rgba(0, 0, 0, 0.05);
  border-top: 1px solid rgba(0, 0, 0, 0.1);
  padding: 15px 0;
  text-align: center;
  margin-top: auto;
  width: 100%;
}

.icp-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.icp-footer a {
  color: #6b7280;
  text-decoration: none;
  font-size: 12px;
  transition: color 0.3s ease;
}

.icp-footer a:hover {
  color: #3b82f6;
}

/* 响应式ICP备案 */
@media (max-width: 768px) {
  .icp-footer {
    padding: 10px 0;
  }
  
  .icp-container {
    padding: 0 15px;
  }
  
  .icp-footer a {
    font-size: 11px;
  }
}
</style> 