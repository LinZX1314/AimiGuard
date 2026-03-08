import { apiClient } from './client'

export interface FixTicket {
  id: number
  finding_id: number | null
  priority: string
  assignee: string | null
  status: string
  due_date: string | null
  resolution_note: string | null
  closed_at: string | null
  trace_id: string
  created_at: string | null
  updated_at: string | null
}

export interface FixTicketListResult {
  total: number
  page: number
  items: FixTicket[]
}

export const fixTicketApi = {
  async list(params?: {
    status?: string
    priority?: string
    page?: number
    page_size?: number
  }): Promise<FixTicketListResult> {
    const res = await apiClient.get('/fix-tickets', { params })
    const d = (res as any)?.data ?? res
    return d as FixTicketListResult
  },

  async create(data: {
    finding_id?: number
    priority?: string
    assignee?: string
    due_date?: string
  }): Promise<FixTicket> {
    const res = await apiClient.post('/fix-tickets', data)
    const d = (res as any)?.data ?? res
    return d as FixTicket
  },

  async get(ticketId: number): Promise<FixTicket> {
    const res = await apiClient.get(`/fix-tickets/${ticketId}`)
    const d = (res as any)?.data ?? res
    return d as FixTicket
  },

  async update(ticketId: number, data: {
    status?: string
    assignee?: string
    priority?: string
    resolution_note?: string
    due_date?: string
  }): Promise<FixTicket> {
    const res = await apiClient.put(`/fix-tickets/${ticketId}`, data)
    const d = (res as any)?.data ?? res
    return d as FixTicket
  },
}
