import { ElMessageBox } from 'element-plus'

/** 破坏性写入前的停顿。取消时抛出，调用方直接 return。 */
export async function confirmStrategyJob(strategy: string, detail: string) {
  await ElMessageBox.confirm(detail, `${strategy} 预计算`, {
    type: 'warning',
    confirmButtonText: '启动预计算',
    cancelButtonText: '取消',
    confirmButtonClass: 'el-button--danger',
  })
}

export async function confirmForceOverwrite(source: string, start: string, end: string) {
  await ElMessageBox.confirm(
    `${source}：${start} 至 ${end} 的已有数据会先删除再写入。`,
    '强制更新',
    {
      type: 'warning',
      confirmButtonText: '仍要覆盖',
      cancelButtonText: '取消',
      confirmButtonClass: 'el-button--danger',
    }
  )
}
