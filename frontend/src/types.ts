export type TaskStatus = 'uploaded' | 'extracting' | 'analyzing' | 'needs_confirmation' | 'ready' | 'failed'

export type Role =
  | 'title'
  | 'subtitle'
  | 'recipient'
  | 'body_paragraph'
  | 'heading_level_1'
  | 'heading_level_2'
  | 'heading_level_3'
  | 'heading_level_4'
  | 'attachment_note'
  | 'attachment_body'
  | 'issuer_name'
  | 'document_date'
  | 'note'
  | 'table'
  | 'image'
  | 'other'

export interface TaskRecord {
  id: string
  filename: string
  status: TaskStatus
  stage: string
  progress: number
  error: string | null
  summary: Record<string, string | number | boolean>
}

export interface StructureItem {
  source_id: string
  role: Role
  confidence: number
  reason?: string | null
}

export interface UncertainItem {
  source_id: string
  suggested_role: Role
  alternatives: Role[]
  reason: string
}

export interface StructurePayload {
  task: TaskRecord
  structure: {
    schema_version: string
    document_type: string
    template_id: string
    items: StructureItem[]
    uncertain_items: UncertainItem[]
  }
  blocks: Record<string, { id: string; type: string; text?: string; rows?: string[][] }>
  warnings: string[]
}

export interface Reports {
  consistency: {
    passed: boolean
    text: { passed: boolean; source_blocks: number; output_blocks: number }
    tables: { passed: boolean; source_count: number; output_count: number }
    images: { passed: boolean; source_count: number; output_count: number }
  }
  format: {
    template_id: string
    page: string[]
    roles: Record<string, number>
    warnings: string[]
  }
}

