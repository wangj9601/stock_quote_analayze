import { apiService } from './api'

export type BoardType = 'industry' | 'concept'

export interface BoardSummary {
  board_code: string
  board_name: string | null
  constituent_count: number
  last_updated: string | null
}

export interface BoardConstituentRow {
  board_code: string
  stock_code: string
  stock_name: string | null
  updated_at: string | null
}

class BoardConstituentsService {
  async listBoards(params: {
    boardType: BoardType
    keyword?: string
    page?: number
    pageSize?: number
  }) {
    const q = new URLSearchParams()
    q.set('board_type', params.boardType)
    if (params.keyword) q.set('keyword', params.keyword)
    q.set('page', String(params.page ?? 1))
    q.set('page_size', String(params.pageSize ?? 30))
    return apiService.get<{
      success: boolean
      data: BoardSummary[]
      total: number
      page: number
      page_size: number
    }>(`/board-constituents/boards?${q}`)
  }

  async listConstituents(params: {
    boardType: BoardType
    boardCode: string
    keyword?: string
    page?: number
    pageSize?: number
  }) {
    const q = new URLSearchParams()
    q.set('board_type', params.boardType)
    q.set('board_code', params.boardCode)
    if (params.keyword) q.set('keyword', params.keyword)
    q.set('page', String(params.page ?? 1))
    q.set('page_size', String(params.pageSize ?? 50))
    return apiService.get<{
      success: boolean
      data: BoardConstituentRow[]
      total: number
      page: number
      page_size: number
      board_code: string
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

  async downloadImportTemplate(format: 'csv' | 'xlsx'): Promise<Blob> {
    return apiService.get(`/board-constituents/import/template?format=${format}`, {
      responseType: 'blob',
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
