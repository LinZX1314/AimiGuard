import { apiClient } from './client'

export interface ReportItem {
  id: number
  report_type: string
  scope?: string
  summary: string
  detail_path?: string | null
  format?: string
  trace_id?: string | null
  file_size?: number | null
  created_at: string
}

export interface ReportContentResult {
  id: number
  report_type: string
  content: string
  file_size: number | null
  created_at: string | null
}

export interface ReportListResult {
  total: number
  page: number
  items: ReportItem[]
}

export const reportApi = {
  async generate(reportType: string, scope?: string) {
    return apiClient.post('/report/generate', {
      report_type: reportType,
      scope
    })
  },

  async getReports(page = 1, pageSize = 10): Promise<ReportListResult> {
    return apiClient.get('/report/reports', { params: { page, page_size: pageSize } })
  },

  async getReport(reportId: number): Promise<ReportItem> {
    return apiClient.get(`/report/reports/${reportId}`)
  },

  async getReportContent(reportId: number): Promise<ReportContentResult> {
    return apiClient.get(`/report/reports/${reportId}/content`)
  }
}
