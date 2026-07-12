import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  ChevronRight,
  Download,
  FileCheck2,
  FileText,
  Info,
  LoaderCircle,
  LockKeyhole,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-react'
import {
  confirmStructure,
  deleteTask,
  downloadUrl,
  getReports,
  getStructure,
  getTask,
  uploadDocument,
} from './api'
import type { Reports, Role, StructurePayload, TaskRecord } from './types'

const ROLE_LABELS: Record<Role, string> = {
  title: '主标题',
  subtitle: '副标题',
  recipient: '主送机关',
  body_paragraph: '正文',
  heading_level_1: '一级标题',
  heading_level_2: '二级标题',
  heading_level_3: '三级标题',
  heading_level_4: '四级标题',
  attachment_note: '附件说明',
  attachment_body: '附件正文',
  issuer_name: '发文机关',
  document_date: '成文日期',
  note: '附注',
  table: '表格',
  image: '图片',
  other: '其他内容',
}

const EDITABLE_ROLES = Object.entries(ROLE_LABELS).filter(([role]) => !['table', 'image'].includes(role)) as [Role, string][]

type View = 'upload' | 'processing' | 'confirm' | 'result'

function App() {
  const [view, setView] = useState<View>('upload')
  const [taskId, setTaskId] = useState(() => localStorage.getItem('formatter_task_id') || '')
  const [task, setTask] = useState<TaskRecord | null>(null)
  const [structure, setStructure] = useState<StructurePayload | null>(null)
  const [reports, setReports] = useState<Reports | null>(null)
  const [error, setError] = useState('')

  const reset = useCallback(async (removeRemote = false) => {
    if (removeRemote && taskId) {
      try { await deleteTask(taskId) } catch { /* The task may already be expired. */ }
    }
    localStorage.removeItem('formatter_task_id')
    setTaskId('')
    setTask(null)
    setStructure(null)
    setReports(null)
    setError('')
    setView('upload')
  }, [taskId])

  useEffect(() => {
    if (!taskId) return
    let active = true
    let timer: number | undefined

    const poll = async () => {
      try {
        const current = await getTask(taskId)
        if (!active) return
        setTask(current)
        setError(current.error || '')
        if (current.status === 'needs_confirmation') {
          const payload = await getStructure(taskId)
          if (!active) return
          setStructure(payload)
          setView('confirm')
          return
        }
        if (current.status === 'ready') {
          const resultReports = await getReports(taskId)
          if (!active) return
          setReports(resultReports)
          setView('result')
          return
        }
        if (current.status === 'failed') {
          setView('processing')
          return
        }
        setView('processing')
        timer = window.setTimeout(poll, 1200)
      } catch (reason) {
        if (!active) return
        setError(reason instanceof Error ? reason.message : '无法连接本机处理服务')
        setView('processing')
      }
    }
    poll()
    return () => {
      active = false
      if (timer) window.clearTimeout(timer)
    }
  }, [taskId])

  const onUploaded = (id: string) => {
    localStorage.setItem('formatter_task_id', id)
    setTaskId(id)
    setError('')
    setView('processing')
  }

  return (
    <div className="app-shell">
      <Header onReset={() => reset(false)} hasTask={Boolean(taskId)} />
      <main>
        <ProgressNav view={view} />
        {view === 'upload' && <UploadView onUploaded={onUploaded} />}
        {view === 'processing' && <ProcessingView task={task} error={error} onRetry={() => window.location.reload()} onReset={() => reset(true)} />}
        {view === 'confirm' && structure && <ConfirmView payload={structure} onConfirmed={() => setView('processing')} setError={setError} />}
        {view === 'result' && task && reports && <ResultView task={task} reports={reports} onDelete={() => reset(true)} />}
      </main>
      <Footer />
    </div>
  )
}

function Header({ onReset, hasTask }: { onReset: () => void; hasTask: boolean }) {
  return (
    <header className="topbar">
      <button className="brand" onClick={onReset} aria-label="返回系统首页">
        <span className="brand-mark"><FileCheck2 size={20} /></span>
        <span><strong>公文格式智能规范化系统</strong><small>山东大学简化规则</small></span>
      </button>
      <div className="topbar-meta">
        <span><ShieldCheck size={16} /> 原文内容保护</span>
        {hasTask && <button className="text-button" onClick={onReset}><RefreshCw size={15} /> 新建任务</button>}
      </div>
    </header>
  )
}

function ProgressNav({ view }: { view: View }) {
  const active = view === 'upload' ? 0 : view === 'processing' ? 1 : view === 'confirm' ? 2 : 3
  const steps = ['上传文档', '智能分析', '确认结构', '下载结果']
  return (
    <nav className="progress-nav" aria-label="处理进度">
      {steps.map((label, index) => (
        <div className={`progress-step ${index === active ? 'active' : ''} ${index < active ? 'done' : ''}`} key={label}>
          <span className="step-index">{index < active ? <Check size={14} /> : index + 1}</span>
          <span>{label}</span>
          {index < steps.length - 1 && <ChevronRight className="step-arrow" size={16} />}
        </div>
      ))}
    </nav>
  )
}

function UploadView({ onUploaded }: { onUploaded: (taskId: string) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const selectFile = (candidate?: File) => {
    if (!candidate) return
    setError('')
    if (!candidate.name.toLowerCase().endsWith('.docx')) return setError('当前仅支持 .docx 文件')
    if (candidate.size > 20 * 1024 * 1024) return setError('文件不能超过 20 MB')
    setFile(candidate)
  }

  const submit = async () => {
    if (!file || !confirmed) return
    setBusy(true)
    setError('')
    try {
      const result = await uploadDocument(file)
      onUploaded(result.task_id)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '上传失败')
      setBusy(false)
    }
  }

  return (
    <section className="workspace upload-workspace">
      <div className="workspace-heading">
        <div><p className="eyebrow">开始规范化</p><h1>上传需要整理的 Word 文档</h1><p>系统识别公文结构并按模板重新生成，原始文字保持不变。</p></div>
        <div className="rule-badge"><Sparkles size={18} /><span>当前规则<strong>山东大学简化公文格式</strong></span></div>
      </div>

      <div
        className={`dropzone ${dragging ? 'dragging' : ''} ${file ? 'has-file' : ''}`}
        onDragEnter={(event) => { event.preventDefault(); setDragging(true) }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => { event.preventDefault(); setDragging(false); selectFile(event.dataTransfer.files[0]) }}
      >
        <input ref={inputRef} type="file" accept=".docx" hidden onChange={(event) => selectFile(event.target.files?.[0])} />
        {file ? (
          <div className="selected-file">
            <span className="file-icon"><FileText size={28} /></span>
            <span><strong>{file.name}</strong><small>{formatBytes(file.size)} · Word 文档</small></span>
            <button className="icon-button" title="移除文件" onClick={() => setFile(null)}><X size={18} /></button>
          </div>
        ) : (
          <button className="dropzone-action" onClick={() => inputRef.current?.click()}>
            <span className="upload-icon"><UploadCloud size={30} /></span>
            <strong>拖放 Word 文档到这里</strong>
            <span>或点击选择文件</span>
            <small>仅支持 .docx，单文件不超过 20 MB</small>
          </button>
        )}
      </div>

      {error && <div className="inline-alert danger"><AlertTriangle size={17} /><span>{error}</span></div>}

      <label className="security-confirm">
        <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
        <span className="custom-checkbox"><Check size={13} /></span>
        <span><strong>我确认该文件不含国家秘密、工作秘密或禁止上传的敏感内容</strong><small>文档内容将由本机后端处理，结构识别信息会发送至外部模型。</small></span>
      </label>

      <div className="action-row">
        <div className="privacy-note"><LockKeyhole size={16} />任务使用随机编号，文件默认 24 小时后删除</div>
        <button className="primary-button" disabled={!file || !confirmed || busy} onClick={submit}>
          {busy ? <LoaderCircle className="spin" size={18} /> : <Sparkles size={18} />}
          {busy ? '正在上传' : '上传并智能分析'}
        </button>
      </div>
    </section>
  )
}

function ProcessingView({ task, error, onRetry, onReset }: { task: TaskRecord | null; error: string; onRetry: () => void; onReset: () => void }) {
  const failed = task?.status === 'failed' || Boolean(error && !task)
  return (
    <section className="workspace processing-workspace">
      <div className={`processing-symbol ${failed ? 'failed' : ''}`}>
        {failed ? <AlertTriangle size={30} /> : <LoaderCircle className="spin" size={30} />}
      </div>
      <p className="eyebrow">{failed ? '处理未完成' : '正在处理'}</p>
      <h1>{failed ? '文档处理遇到问题' : task?.stage || '正在连接本机处理服务'}</h1>
      <p className="processing-copy">{failed ? (error || task?.error) : '系统正在提取内容并识别语义结构，不会改写原始文字。'}</p>
      <div className="progress-track"><span style={{ width: `${task?.progress || 4}%` }} /></div>
      <div className="progress-detail"><span>{task?.filename || '等待任务信息'}</span><strong>{task?.progress || 0}%</strong></div>
      {task?.summary && Object.keys(task.summary).length > 0 && (
        <div className="metric-strip">
          <Metric label="段落" value={task.summary.paragraphs ?? '—'} />
          <Metric label="表格" value={task.summary.tables ?? '—'} />
          <Metric label="图片" value={task.summary.images ?? '—'} />
          <Metric label="识别方式" value={task.summary.analysis_engine === 'deepseek' ? '智能模型' : '本地规则'} />
        </div>
      )}
      {failed && <div className="button-pair"><button className="secondary-button" onClick={onReset}><Trash2 size={17} />删除任务</button><button className="primary-button" onClick={onRetry}><RefreshCw size={17} />重新连接</button></div>}
    </section>
  )
}

function ConfirmView({ payload, onConfirmed, setError }: { payload: StructurePayload; onConfirmed: () => void; setError: (value: string) => void }) {
  const [items, setItems] = useState(payload.structure.items)
  const [busy, setBusy] = useState(false)
  const uncertainIds = new Set(payload.structure.uncertain_items.map((item) => item.source_id))
  const visibleItems = items.filter((item) => uncertainIds.has(item.source_id))
  const summary = useMemo(() => {
    const counts: Record<string, number> = {}
    items.forEach((item) => { counts[item.role] = (counts[item.role] || 0) + 1 })
    return counts
  }, [items])

  const updateRole = (sourceId: string, role: Role) => {
    setItems((current) => current.map((item) => item.source_id === sourceId ? { ...item, role, confidence: 1 } : item))
  }

  const submit = async () => {
    setBusy(true)
    setError('')
    try {
      await confirmStructure(payload.task.id, items)
      onConfirmed()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '提交结构失败')
      setBusy(false)
    }
  }

  return (
    <section className="workspace confirm-workspace">
      <div className="workspace-heading compact-heading">
        <div><p className="eyebrow">结构识别完成</p><h1>确认文档结构</h1><p>系统只展示不确定项；未显示的内容将按识别结果处理。</p></div>
        <span className="confidence-badge"><CheckCircle2 size={17} />{visibleItems.length ? `${visibleItems.length} 项待确认` : '未发现疑难项'}</span>
      </div>

      <div className="document-summary">
        <SummaryItem label="文种" value={payload.structure.document_type === 'unknown' ? '未识别' : payload.structure.document_type} />
        <SummaryItem label="主标题" value={summary.title || 0} />
        <SummaryItem label="正文段落" value={summary.body_paragraph || 0} />
        <SummaryItem label="层级标题" value={(summary.heading_level_1 || 0) + (summary.heading_level_2 || 0) + (summary.heading_level_3 || 0) + (summary.heading_level_4 || 0)} />
        <SummaryItem label="表格 / 图片" value={`${summary.table || 0} / ${summary.image || 0}`} />
      </div>

      {payload.warnings.map((warning) => <div className="inline-alert warning" key={warning}><Info size={17} /><span>{warning}</span></div>)}

      {visibleItems.length ? (
        <div className="uncertain-list">
          {visibleItems.map((item) => {
            const block = payload.blocks[item.source_id]
            const detail = payload.structure.uncertain_items.find((entry) => entry.source_id === item.source_id)
            return (
              <article className="uncertain-row" key={item.source_id}>
                <div><span className="source-id">{item.source_id}</span><p>{block?.text || '非文本内容块'}</p><small>{detail?.reason || item.reason}</small></div>
                <label><span>内容角色</span><select value={item.role} onChange={(event) => updateRole(item.source_id, event.target.value as Role)}>{EDITABLE_ROLES.map(([role, label]) => <option value={role} key={role}>{label}</option>)}</select></label>
              </article>
            )
          })}
        </div>
      ) : (
        <div className="all-clear"><CheckCircle2 size={24} /><div><strong>结构识别结果完整</strong><p>每个原始内容块均已分配角色，可以按当前模板生成。</p></div></div>
      )}

      <div className="action-row confirm-actions">
        <span className="privacy-note"><ShieldCheck size={16} />每个内容块都会保留并参与一致性校验</span>
        <button className="primary-button" disabled={busy} onClick={submit}>{busy ? <LoaderCircle className="spin" size={18} /> : <FileCheck2 size={18} />}{busy ? '正在提交' : '确认结构并生成文档'}</button>
      </div>
    </section>
  )
}

function ResultView({ task, reports, onDelete }: { task: TaskRecord; reports: Reports; onDelete: () => void }) {
  return (
    <section className="workspace result-workspace">
      <div className="result-heading"><span className="success-symbol"><Check size={30} /></span><div><p className="eyebrow">处理完成</p><h1>规范文档已生成</h1><p>内容一致性检查已通过，可以下载并继续编辑。</p></div></div>
      <div className="result-file"><span className="file-icon"><FileText size={28} /></span><span><strong>{task.filename.replace(/\.docx$/i, '')}_格式规范版.docx</strong><small>山东大学简化公文格式</small></span><a className="primary-button" href={downloadUrl(task.id)}><Download size={18} />下载规范版 Word</a></div>

      <div className="report-grid">
        <ReportStatus title="原始文本" passed={reports.consistency.text.passed} detail={`${reports.consistency.text.source_blocks} 个文本块全部保留`} />
        <ReportStatus title="表格内容" passed={reports.consistency.tables.passed} detail={`${reports.consistency.tables.source_count} 个表格内容一致`} />
        <ReportStatus title="图片完整性" passed={reports.consistency.images.passed} detail={`${reports.consistency.images.source_count} 张图片哈希一致`} />
      </div>

      <div className="format-summary"><div><h2>本次格式处理</h2><p>{reports.format.page.join(' · ')}</p></div><div className="role-counts">{Object.entries(reports.format.roles).filter(([, count]) => count > 0).map(([role, count]) => <span key={role}>{ROLE_LABELS[role as Role] || role}<strong>{count}</strong></span>)}</div></div>
      <div className="action-row result-actions"><span className="privacy-note"><Info size={16} />请使用 Microsoft Word 或 WPS 打开并进行最终人工复核</span><button className="secondary-button danger-text" onClick={onDelete}><Trash2 size={17} />立即删除任务文件</button></div>
    </section>
  )
}

function Metric({ label, value }: { label: string; value: string | number | boolean }) { return <div><small>{label}</small><strong>{String(value)}</strong></div> }
function SummaryItem({ label, value }: { label: string; value: string | number }) { return <div><small>{label}</small><strong>{value}</strong></div> }
function ReportStatus({ title, passed, detail }: { title: string; passed: boolean; detail: string }) { return <article className="report-status"><span className={passed ? 'pass' : 'fail'}>{passed ? <Check size={17} /> : <X size={17} />}</span><div><strong>{title}</strong><p>{detail}</p></div></article> }
function Footer() { return <footer><span>公文格式智能规范化系统</span><span>仅用于非涉密办公文档格式整理</span></footer> }
function formatBytes(bytes: number) { return bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB` }

export default App

