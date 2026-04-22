import type { Locator, Page } from '@playwright/test'

export interface UserFormData {
  username: string
  email: string
  password?: string
  role: 'admin' | 'user' | 'guest'
}

export class UsersPage {
  readonly page: Page
  readonly searchInput: Locator
  readonly createUserButton: Locator
  readonly userTable: Locator
  readonly dialog: Locator

  constructor(page: Page) {
    this.page = page
    this.searchInput = page.getByPlaceholder('搜索用户名或邮箱')
    this.createUserButton = page.getByRole('button', { name: '新增用户' })
    this.userTable = page.locator('.table-section table')
    this.dialog = page.getByRole('dialog')
  }

  async goto() {
    await this.page.goto('/users')
  }

  async searchUser(keyword: string) {
    await this.searchInput.fill(keyword)
    // 页面通常有防抖或按回车搜索
    await this.page.keyboard.press('Enter')
    await this.page.waitForLoadState('networkidle')
  }

  async createUser(data: UserFormData) {
    await this.createUserButton.click()
    
    await this.dialog.getByPlaceholder('请输入用户名').fill(data.username)
    await this.dialog.getByPlaceholder('请输入邮箱地址').fill(data.email)
    if (data.password) {
      await this.dialog.getByPlaceholder('请输入密码').fill(data.password)
    }
    
    // 处理 Element Plus Select（新版为带标签的 combobox，无 placeholder）
    const roleSelect = this.dialog.locator('.el-form-item').filter({ hasText: '角色' }).locator('.el-select').first()
    await roleSelect.click({ force: true })
    const roleLabel = {
      admin: '管理员',
      user: '用户',
      guest: '访客'
    }[data.role]
    await this.page.getByRole('option', { name: roleLabel }).first().click()

    await this.dialog.getByRole('button', { name: '确定' }).click()
  }

  async getUserRow(username: string): Promise<Locator> {
    return this.userTable.locator('tr').filter({ hasText: username })
  }

  async isUserInList(username: string): Promise<boolean> {
    const row = await this.getUserRow(username)
    return (await row.count()) > 0
  }
}
