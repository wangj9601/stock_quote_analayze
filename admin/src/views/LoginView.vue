<template>
  <div class="login-shell">
    <div class="login-card">
      <div>
        <h2 class="login-brand">
          冰枫堂
        </h2>
        <p class="login-sub">
          管理端
        </p>
      </div>
      <form class="mt-8 space-y-6" @submit.prevent="handleLogin">
        <div class="login-fields">
          <div>
            <label for="username" class="sr-only">用户名</label>
            <input
              id="username"
              v-model="form.username"
              name="username"
              type="text"
              required
              class="login-field login-field-top"
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
              class="login-field login-field-bottom"
              placeholder="密码"
            />
          </div>
        </div>

        <div>
          <button
            type="submit"
            :disabled="loading"
            class="login-submit"
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
.login-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f3f1ec;
  color: #1a2332;
  padding: 3rem 1rem 0;
}

.login-brand {
  margin: 0;
  text-align: center;
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: #234e70;
}

.login-sub {
  margin: 8px 0 0;
  text-align: center;
  font-size: 13px;
  color: #3e4c59;
}

.login-field {
  display: block;
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #c9c3b8;
  background: #fff;
  color: #1a2332;
  font: inherit;
  font-size: 14px;
}

.login-field-top {
  border-bottom: none;
}

.login-field:focus {
  outline: 2px solid #234e70;
  outline-offset: 1px;
  position: relative;
  z-index: 1;
}

.login-submit {
  position: relative;
  width: 100%;
  padding: 10px 16px;
  border: 1px solid #234e70;
  border-radius: 2px;
  background: #234e70;
  color: #f3f1ec;
  font: inherit;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.08em;
  cursor: pointer;
}

.login-submit:hover {
  background: #1b3d58;
}

.login-submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.login-submit:focus-visible {
  outline: 2px solid #d7b56d;
  outline-offset: 2px;
}

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
  gap: 1.5rem;
  background: #fff;
  padding: 2rem;
  border: 1px solid #c9c3b8;
  border-radius: 2px;
  box-shadow: 0 10px 24px rgba(26, 35, 50, 0.08);
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
  background: transparent;
  border-top: 1px solid #c9c3b8;
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
  color: #3e4c59;
  text-decoration: none;
  font-size: 12px;
  transition: color 0.3s ease;
}

.icp-footer a:hover {
  color: #234e70;
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