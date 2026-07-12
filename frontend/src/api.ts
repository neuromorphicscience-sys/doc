import type { Reports, StructureItem, StructurePayload, TaskRecord } from './types'

export const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '')

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const body = await response.json()
      message = body.detail || message
    } catch {
      // Keep the HTTP fallback message.
    }
    throw new Error(message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export async function uploadDocument(file: File): Promise<{ task_id: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('security_confirmed', 'true')
  return request('/tasks', { method: 'POST', body: form })
}

export const getTask = (taskId: string) => request<TaskRecord>(`/tasks/${taskId}`)
export const getStructure = (taskId: string) => request<StructurePayload>(`/tasks/${taskId}/structure`)
export const getReports = (taskId: string) => request<Reports>(`/tasks/${taskId}/reports`)

export const confirmStructure = (taskId: string, items: StructureItem[]) =>
  request(`/tasks/${taskId}/structure`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ items }),
  })

export const deleteTask = (taskId: string) => request<void>(`/tasks/${taskId}`, { method: 'DELETE' })
export const downloadUrl = (taskId: string) => `${API_BASE}/tasks/${taskId}/download`

