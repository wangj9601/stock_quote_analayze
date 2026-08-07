import { apiService } from './api'

export type BoardType = 'industry' | 'concept'

export interface BoardSummary {
  board_code: string
  board_name: string | null
  constituent_count: number
  last_updated: string | null
  trade_observe_flag?: boolean
  frontend_visible_flag?: boolean
  board_code_source?: string
  board_code_source_label?: string
}

export interface BoardCodeSourceOption {
  value: string
  label: string
}

export interface BoardConstituentRow {
  board_code: string
  stock_code: string
  stock_name: string | null
  updated_at: string | null
  board_role?: 'leader' | 'mid' | string | null
  board_role_label?: string | null
  board_role_score?: number | null
  role_reason?: string | null
  change_percent?: number | null
}

class BoardConstituentsService {
  async listBoards(params: {
    boardType: BoardType
    keyword?: string
    boardCodeSource?: string
    sortBy?: string
    sortOrder?: 'asc' | 'desc'
    page?: number
    pageSize?: number
  }) {
    const q = new URLSearchParams()
    q.set('board_type', params.boardType)
    if (params.keyword) q.set('keyword', params.keyword)
    if (params.boardCodeSource && params.boardCodeSource !== 'all') {
      q.set('board_code_source', params.boardCodeSource)
    }
    if (params.sortBy) q.set('sort_by', params.sortBy)
    if (params.sortOrder) q.set('sort_order', params.sortOrder)
    q.set('page', String(params.page ?? 1))
    q.set('page_size', String(params.pageSize ?? 50))
    return apiService.get<{
      success: boolean
      data: BoardSummary[]
      total: number
      page: number
      page_size: number
      sort_by?: string
      sort_order?: string
      board_code_source?: string | null
    }>(`/board-constituents/boards?${q}`)
  }

  async listBoardsByStock(params: { boardType: BoardType; stock: string }) {
    const q = new URLSearchParams()
    q.set('board_type', params.boardType)
    q.set('stock', params.stock.trim())
    return apiService.get<{
      success: boolean
      message?: string
      data: {
        stock_codes: string[]
        stock_names: string[]
        boards: Array<{
          board_code: string
          board_name: string | null
          last_updated: string | null
          trade_observe_flag?: boolean
        }>
        total: number
      }
    }>(`/board-constituents/boards/by-stock?${q}`)
  }

  async listConstituents(params: {
    boardType: BoardType
    boardCode: string
    keyword?: string
    page?: number
    pageSize?: number
    boardCodeSource?: string
  }) {
    const q = new URLSearchParams()
    q.set('board_type', params.boardType)
    q.set('board_code', params.boardCode)
    if (params.keyword) q.set('keyword', params.keyword)
    if (params.boardCodeSource) q.set('board_code_source', params.boardCodeSource)
    q.set('page', String(params.page ?? 1))
    q.set('page_size', String(params.pageSize ?? 50))
    return apiService.get<{
      success: boolean
      data: BoardConstituentRow[]
      total: number
      page: number
      page_size: number
      board_code: string
      board_code_source?: string
      board_code_source_label?: string
      board_change_percent_est?: number | null
      roles_computed?: boolean
      role_leaders?: BoardConstituentRow[]
      role_mids?: BoardConstituentRow[]
    }>(`/board-constituents/list?${q}`)
  }

  async addStocks(body: {
    boardType: BoardType
    boardCode: string
    stocks: Array<{ stock_code: string; stock_name?: string }>
  }) {
    return apiService.post<{ success: boolean; message?: string }>('/board-constituents/add', {
      board_type: body.boardType,
      board_code: body.boardCode,
      stocks: body.stocks,
    })
  }

  async removeStocks(body: {
    boardType: BoardType
    boardCode: string
    scope: 'selected' | 'all'
    stockCodes?: string[]
  }) {
    return apiService.post<{ success: boolean; message?: string; data?: { deleted: number } }>(
      '/board-constituents/remove',
      {
        board_type: body.boardType,
        board_code: body.boardCode,
        scope: body.scope,
        stock_codes: body.stockCodes,
      }
    )
  }

  async syncConstituents(body: {
    boardType: BoardType
    boardCodes?: string[]
    syncBoardList?: boolean
  }) {
    return apiService.post<{ success: boolean; message?: string }>('/board-constituents/sync', {
      board_type: body.boardType,
      board_codes: body.boardCodes,
      sync_board_list: body.syncBoardList ?? false,
    })
  }

  async getBoardCodeSources() {
    return apiService.get<{
      success: boolean
      data: BoardCodeSourceOption[]
    }>('/board-constituents/boards/code-sources')
  }

  async saveBoard(body: {
    boardType: BoardType
    boardCode?: string
    boardName?: string
    originalBoardCode?: string
    tradeObserveFlag?: boolean
    frontendVisibleFlag?: boolean
    boardCodeSource?: string
  }) {
    return apiService.post<{
      success: boolean
      message?: string
      data?: {
        action: string
        board_code: string
        board_name: string | null
        trade_observe_flag?: boolean
        frontend_visible_flag?: boolean
        original_board_code?: string | null
      }
    }>('/board-constituents/boards/save', {
      board_type: body.boardType,
      board_code: body.boardCode,
      board_name: body.boardName,
      original_board_code: body.originalBoardCode,
      trade_observe_flag: body.tradeObserveFlag,
      frontend_visible_flag: body.frontendVisibleFlag,
      board_code_source: body.boardCodeSource,
    })
  }

  async setBoardTradeObserve(body: {
    boardType: BoardType
    boardCode: string
    tradeObserveFlag: boolean
  }) {
    return apiService.post<{
      success: boolean
      message?: string
      data?: { board_code: string; trade_observe_flag: boolean }
    }>('/board-constituents/boards/trade-observe', {
      board_type: body.boardType,
      board_code: body.boardCode,
      trade_observe_flag: body.tradeObserveFlag,
    })
  }

  async setBoardFrontendVisible(body: {
    boardType: BoardType
    boardCode: string
    frontendVisibleFlag: boolean
  }) {
    return apiService.post<{
      success: boolean
      message?: string
      data?: { board_code: string; frontend_visible_flag: boolean }
    }>('/board-constituents/boards/frontend-visible', {
      board_type: body.boardType,
      board_code: body.boardCode,
      frontend_visible_flag: body.frontendVisibleFlag,
    })
  }

  async getNextBoardCode(boardType: BoardType, afterCode?: string) {
    const q = new URLSearchParams()
    q.set('board_type', boardType)
    if (afterCode) q.set('after_code', afterCode)
    return apiService.get<{
      success: boolean
      data: { board_code: string }
    }>(`/board-constituents/boards/next-code?${q}`)
  }

  async deleteBoard(body: { boardType: BoardType; boardCode: string }) {
    return apiService.post<{
      success: boolean
      message?: string
      data?: { constituents_deleted: number }
    }>('/board-constituents/boards/delete', {
      board_type: body.boardType,
      board_code: body.boardCode,
    })
  }

  async deleteBoardsBatch(body: { boardType: BoardType; boardCodes: string[] }) {
    return apiService.post<{
      success: boolean
      message?: string
      data?: {
        board_codes: string[]
        boards_deleted: number
        constituents_deleted: number
      }
    }>('/board-constituents/boards/delete-batch', {
      board_type: body.boardType,
      board_codes: body.boardCodes,
    })
  }

  async downloadImportTemplate(format: 'csv' | 'xlsx'): Promise<Blob> {
    return apiService.get(`/board-constituents/import/template?format=${format}`, {
      responseType: 'blob',
    })
  }

  async downloadAllImportTemplate(format: 'csv' | 'xlsx'): Promise<Blob> {
    return apiService.get(`/board-constituents/import/all/template?format=${format}`, {
      responseType: 'blob',
    })
  }

  async exportAll(params: { boardType: BoardType; format?: 'csv' | 'xlsx' }): Promise<Blob> {
    const q = new URLSearchParams()
    q.set('board_type', params.boardType)
    q.set('format', params.format ?? 'xlsx')
    return apiService.get(`/board-constituents/export/all?${q}`, {
      responseType: 'blob',
    })
  }

  async importAllFromFile(params: { boardType: BoardType; file: File; clearExisting?: boolean }) {
    const fd = new FormData()
    fd.append('file', params.file)
    const q = new URLSearchParams()
    q.set('board_type', params.boardType)
    if (params.clearExisting) {
      q.set('clear_existing', 'true')
    }
    return apiService.post<{
      success: boolean
      message?: string
      data?: {
        boards_processed: number
        basic_synced?: number
        cleared_basic?: number
        cleared_constituents?: number
        cleared_realtime?: number
        processed: number
        added: number
        skipped_issues: number
        issues: Array<{ row_no: number; message: string; board_code?: string; stock_code?: string }>
        board_stats: Array<{ board_code: string; processed: number; added: number }>
      }
    }>(`/board-constituents/import/all?${q.toString()}`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  }

  async importFromFile(params: {
    boardType: BoardType
    boardCode: string
    file: File
  }) {
    const fd = new FormData()
    fd.append('file', params.file)
    const q = new URLSearchParams()
    q.set('board_type', params.boardType)
    q.set('board_code', params.boardCode)
    return apiService.post<{
      success: boolean
      message?: string
      data?: {
        processed: number
        added: number
        skipped_issues: number
        issues: Array<{ row_no: number; message: string; stock_code?: string }>
      }
    }>(`/board-constituents/import?${q.toString()}`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  }
}

export const boardConstituentsService = new BoardConstituentsService()
