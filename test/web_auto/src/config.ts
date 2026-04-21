import dotenv from 'dotenv'

dotenv.config({ path: '.env.web-auto' })

export type LoginMode = 'account_password' | 'storage_state' | 'manual_captcha'

export interface WebAutoConfig {
  baseUrl: string
  username: string
  password: string
  loginMode: LoginMode
  storageStatePath: string
  captchaBypassHeaderKey?: string
  captchaBypassHeaderValue?: string
}

function getLoginMode(raw: string | undefined): LoginMode {
  if (raw === 'storage_state' || raw === 'manual_captcha') {
    return raw
  }
  return 'account_password'
}

export const config: WebAutoConfig = {
  baseUrl: process.env.WEB_BASE_URL ?? 'http://127.0.0.1:3000',
  username: process.env.WEB_USERNAME ?? '',
  password: process.env.WEB_PASSWORD ?? '',
  loginMode: getLoginMode(process.env.LOGIN_MODE),
  storageStatePath: process.env.STORAGE_STATE_PATH ?? '.auth/storage-state.json',
  captchaBypassHeaderKey: process.env.CAPTCHA_BYPASS_HEADER_KEY,
  captchaBypassHeaderValue: process.env.CAPTCHA_BYPASS_HEADER_VALUE
}

