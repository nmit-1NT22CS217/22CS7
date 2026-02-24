
import { useEffect, useMemo, useRef, useState } from 'react'
import './App.css'

const METRICS = [
  { key: 'drift_score', label: 'Drift Score' },
  { key: 'confidence_score', label: 'Confidence' },
  { key: 'semantic_drift', label: 'Semantic Drift' },
  { key: 'anomaly_score', label: 'Anomaly' },
]

const SAMPLE_TEXT = `Hello support, I need help with my credit card profile. My name is Sarah Mitchell and my email is sarah.mitchell@techcorp.com.
My phone number is +1 (555) 789-0123 and my billing address is 456 Oak Street, Portland, OR 97204.
My backup card is 4532-1234-5678-9012 and my account ID is ACC-2024-56789.
Please update the profile and confirm once done.`

function formatNumber(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(digits)
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function buildHighlightHtml(text, detectedPii) {
  if (!text) return '&nbsp;'
  const ranges = []
  Object.values(detectedPii || {}).forEach((values) => {
    if (!Array.isArray(values)) return
    values.forEach((value) => {
      if (!value || value.length < 2) return
      let start = 0
      while (true) {
        const index = text.indexOf(value, start)
        if (index === -1) break
        ranges.push({ start: index, end: index + value.length })
        start = index + value.length
      }
    })
  })

  if (!ranges.length) {
    return escapeHtml(text)
  }

  ranges.sort((a, b) => a.start - b.start || b.end - a.end)
  const merged = []
  ranges.forEach((range) => {
    const last = merged[merged.length - 1]
    if (!last || range.start > last.end) {
      merged.push({ ...range })
      return
    }
    if (range.end > last.end) {
      last.end = range.end
    }
  })

  let result = ''
  let cursor = 0
  merged.forEach((range) => {
    result += escapeHtml(text.slice(cursor, range.start))
    result += `<mark class="pii-mark">${escapeHtml(text.slice(range.start, range.end))}</mark>`
    cursor = range.end
  })
  result += escapeHtml(text.slice(cursor))
  return result || '&nbsp;'
}

function BarChart({ data }) {
  if (!data || data.length === 0) {
    return <div className="chart-empty">No PII detected yet.</div>
  }

  const max = Math.max(...data.map((d) => d.count), 1)
  return (
    <div className="bar-chart">
      {data.map((item) => (
        <div key={item.label} className="bar-row">
          <div className="bar-label">{item.label}</div>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(item.count / max) * 100}%` }} />
          </div>
          <div className="bar-value">{item.count}</div>
        </div>
      ))}
    </div>
  )
}

function PieChart({ data }) {
  if (!data || data.length === 0) {
    return <div className="chart-empty">No PII detected yet.</div>
  }

  const total = data.reduce((sum, item) => sum + item.count, 0) || 1
  let cumulative = 0
  const colors = ['#f97316', '#0ea5e9', '#10b981', '#ef4444', '#8b5cf6', '#22d3ee']
  const segments = data.map((item, index) => {
    const value = item.count / total
    const start = cumulative
    const end = cumulative + value
    cumulative = end
    const largeArc = end - start > 0.5 ? 1 : 0
    const startAngle = start * Math.PI * 2 - Math.PI / 2
    const endAngle = end * Math.PI * 2 - Math.PI / 2
    const x1 = 50 + 45 * Math.cos(startAngle)
    const y1 = 50 + 45 * Math.sin(startAngle)
    const x2 = 50 + 45 * Math.cos(endAngle)
    const y2 = 50 + 45 * Math.sin(endAngle)
    const path = `M 50 50 L ${x1} ${y1} A 45 45 0 ${largeArc} 1 ${x2} ${y2} Z`
    return { path, color: colors[index % colors.length], label: item.label }
  })

  return (
    <div className="pie-wrap">
      <svg viewBox="0 0 100 100" className="pie">
        {segments.map((seg) => (
          <path key={seg.label} d={seg.path} fill={seg.color} />
        ))}
      </svg>
      <div className="pie-legend">
        {data.slice(0, 6).map((item, idx) => (
          <div key={item.label} className="legend-row">
            <span className="legend-dot" style={{ background: colors[idx % colors.length] }} />
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function LineChart({ series, height = 160 }) {
  const flattened = series.flatMap((s) => s.values)
  const numeric = flattened.filter((v) => Number.isFinite(v))
  if (!numeric.length) {
    return <div className="chart-empty">Not enough data.</div>
  }

  const width = 320
  const min = Math.min(...numeric)
  const max = Math.max(...numeric)
  const span = max - min || 1
  const padding = { top: 8, right: 8, bottom: 24, left: 34 }
  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom

  const pointsToPath = (values) => {
    const step = plotWidth / (values.length - 1 || 1)
    return values
      .map((v, i) => {
        if (!Number.isFinite(v)) return null
        const x = padding.left + i * step
        const y = padding.top + (1 - (v - min) / span) * plotHeight
        return `${x},${y}`
      })
      .filter(Boolean)
      .join(' ')
  }

  const yTicks = 4
  const yTickValues = Array.from({ length: yTicks }, (_, i) => min + (span * i) / (yTicks - 1))

  return (
    <div className="line-chart">
      <svg viewBox={`0 0 ${width} ${height}`}>
        <line
          x1={padding.left}
          y1={padding.top}
          x2={padding.left}
          y2={height - padding.bottom}
          stroke="rgba(255,255,255,0.2)"
          strokeWidth="1"
        />
        <line
          x1={padding.left}
          y1={height - padding.bottom}
          x2={width - padding.right}
          y2={height - padding.bottom}
          stroke="rgba(255,255,255,0.2)"
          strokeWidth="1"
        />
        {yTickValues.map((value, idx) => {
          const y = padding.top + (1 - (value - min) / span) * plotHeight
          return (
            <g key={`ytick-${idx}`}>
              <line
                x1={padding.left - 4}
                y1={y}
                x2={padding.left}
                y2={y}
                stroke="rgba(255,255,255,0.2)"
              />
              <text x={2} y={y + 3} fontSize="9" fill="rgba(255,255,255,0.55)">
                {value.toFixed(2)}
              </text>
            </g>
          )
        })}
        <text x={padding.left} y={height - 6} fontSize="9" fill="rgba(255,255,255,0.55)">
          t0
        </text>
        <text x={width - padding.right - 12} y={height - 6} fontSize="9" fill="rgba(255,255,255,0.55)">
          tN
        </text>
        {series.map((s) => (
          <polyline
            key={s.label}
            fill="none"
            stroke={s.color}
            strokeWidth="2.4"
            points={pointsToPath(s.values)}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}
      </svg>
      <div className="chart-legend">
        {series.map((s) => (
          <div key={s.label} className="legend-row">
            <span className="legend-dot" style={{ background: s.color }} />
            <span>{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
function App() {
  const apiBase =
    import.meta.env.VITE_API_BASE ||
    (import.meta.env.DEV && typeof window !== 'undefined' && window.location.port === '5173'
      ? 'http://localhost:5000'
      : '')
  const ocrBase = import.meta.env.VITE_OCR_BASE || apiBase
  const modelBase = import.meta.env.VITE_MODEL_BASE || apiBase
  const fileInputRef = useRef(null)
  const textareaRef = useRef(null)
  const highlightRef = useRef(null)

  const [inputText, setInputText] = useState('')
  const [instructions, setInstructions] = useState('')
  const [mode, setMode] = useState('pseudonymize')
  const [callLlm] = useState(true)
  const [loading, setLoading] = useState(false)
  const [ocrLoading, setOcrLoading] = useState(false)
  const [error, setError] = useState('')

  const [messages, setMessages] = useState([])
  const [lastResult, setLastResult] = useState(null)
  const [piiCategories, setPiiCategories] = useState([])
  const [selectedLabels, setSelectedLabels] = useState({})
  const [detectedPii, setDetectedPii] = useState({})
  const [driftPoints, setDriftPoints] = useState([])
  const [driftWindow, setDriftWindow] = useState(20)
  const [nlpMode, setNlpMode] = useState('primary')
  const [distributionMode, setDistributionMode] = useState('primary')
  const [timeMode, setTimeMode] = useState('primary')
  const [riskMode, setRiskMode] = useState('primary')

  const [files, setFiles] = useState([])
  const [promptBox, setPromptBox] = useState('')

  const [modelStatus, setModelStatus] = useState(null)
  const [labelStats, setLabelStats] = useState(null)
  const [training, setTraining] = useState(false)
  const [storedMappings, setStoredMappings] = useState([])
  const [mappingsLoading, setMappingsLoading] = useState(false)

  const highlightHtml = useMemo(
    () => buildHighlightHtml(inputText, detectedPii),
    [inputText, detectedPii]
  )

  const driftSummary = useMemo(() => {
    if (!lastResult?.drift_analysis) return null
    return METRICS.map((metric) => ({
      key: metric.key,
      label: metric.label,
      value: lastResult.drift_analysis[metric.key],
    }))
  }, [lastResult])

  const totalEntities = useMemo(
    () => piiCategories.reduce((sum, item) => sum + item.count, 0),
    [piiCategories]
  )

  const lockedLabels = useMemo(
    () => piiCategories.filter((item) => item.locked).map((item) => item.label),
    [piiCategories]
  )

  const windowedDrift = useMemo(() => {
    if (!driftPoints?.length) return []
    return driftPoints.slice(-driftWindow)
  }, [driftPoints, driftWindow])

  useEffect(() => {
    refreshModelStatus()
    loadDriftHistory()
    loadMappings()
  }, [])

  useEffect(() => {
    syncTextareaHeight()
    if (!inputText.trim()) return
    const handle = setTimeout(() => {
      detectOnly(inputText)
    }, 500)
    return () => clearTimeout(handle)
  }, [inputText])

  useEffect(() => {
    if (!inputText.trim()) return
    const handle = setTimeout(() => {
      runPipeline(inputText, {
        replaceInput: true,
        callLlmOverride: false,
        suppressMessages: true,
      })
    }, 500)
    return () => clearTimeout(handle)
  }, [mode])

  async function readJson(response) {
    const data = await response.json().catch(() => ({}))
    if (!response.ok) {
      const message = data?.error || `${response.status} ${response.statusText}`
      throw new Error(message)
    }
    return data
  }

  function deriveSelections(categories, prev) {
    const next = { ...prev }
    categories.forEach((item) => {
      if (!(item.label in next)) {
        next[item.label] = !item.locked
      }
    })
    Object.keys(next).forEach((label) => {
      if (!categories.find((item) => item.label === label)) {
        delete next[label]
      }
    })
    return next
  }

  async function detectOnly(text) {
    const trimmed = text.trim()
    if (!trimmed) return
    try {
      const detectData = await fetch(`${apiBase}/api/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: trimmed }),
      }).then(readJson)
      const categories = detectData?.pii_categories || []
      const nextSelections = deriveSelections(categories, selectedLabels)
      setPiiCategories(categories)
      setSelectedLabels(nextSelections)
      setDetectedPii(detectData?.detected_pii || {})
    } catch {
      // Silent on background detection
    }
  }

  function buildAllowedLabels(categories, selections) {
    const allowed = []
    categories.forEach((item) => {
      if (item.locked) {
        allowed.push(item.label)
      } else if (selections[item.label]) {
        allowed.push(item.label)
      }
    })
    return allowed
  }

  async function runPipeline(text, options = {}) {
    const { replaceInput = false, callLlmOverride, suppressMessages = false } = options
    const trimmed = text.trim()
    if (!trimmed) return

    setLoading(true)
    setError('')
    setLastResult(null)
    const deferUserMessage = replaceInput && !suppressMessages
    if (!suppressMessages && !deferUserMessage) {
      setMessages((prev) => [...prev, { role: 'user', content: trimmed }])
    }

    try {
      const detectRequest = fetch(`${apiBase}/api/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: trimmed }),
      }).then(readJson)

      const [detectData] = await Promise.all([detectRequest])
      const categories = detectData?.pii_categories || []
      const nextSelections = deriveSelections(categories, selectedLabels)
      setPiiCategories(categories)
      setSelectedLabels(nextSelections)
      setDetectedPii(detectData?.detected_pii || {})

      const allowed_labels = buildAllowedLabels(categories, nextSelections)
      const anonymizeData = await fetch(`${apiBase}/api/anonymize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: trimmed,
          mode,
          call_llm: callLlmOverride ?? callLlm,
          scenario: instructions,
          allowed_labels: allowed_labels.length ? allowed_labels : undefined,
        }),
      }).then(readJson)

      setDriftPoints(anonymizeData?.drift_history_points || [])
      setLastResult(anonymizeData)

      if (replaceInput && anonymizeData?.anonymized_text) {
        setInputText(anonymizeData.anonymized_text)
      }

      const assistantText =
        anonymizeData?.deanonymized_output ||
        anonymizeData?.llm_response_anonymized ||
        anonymizeData?.anonymized_text ||
        'No response returned.'

      if (!suppressMessages && deferUserMessage) {
        const userMessage = anonymizeData?.anonymized_text || trimmed
        setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
      }

      if (!suppressMessages) {
        setMessages((prev) => [...prev, { role: 'assistant', content: assistantText }])
      }

      // Send the anonymized prompt to drift service and refresh graphs
      try {
        const driftResp = await fetch(`${modelBase}/analyze`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: anonymizeData?.anonymized_text || trimmed }),
        }).then(readJson)
        if (driftResp?.analysis) {
          setLastResult((prev) => ({
            ...prev,
            drift_analysis: driftResp.analysis,
            drift_available: true,
          }))
        }
        await loadDriftHistory()
      } catch {
        // Ignore drift errors to avoid blocking the main flow
      }

      if (anonymizeData?.mappings_count) {
        await loadMappings()
      }
    } catch (err) {
      setError(err.message || 'Something went wrong.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    await runPipeline(inputText, { replaceInput: true })
  }

  async function anonymizeOnly() {
    const trimmed = inputText.trim()
    if (!trimmed) return
    await runPipeline(trimmed, {
      replaceInput: true,
      callLlmOverride: false,
      suppressMessages: true,
    })
  }

  async function extractAndAnonymize(filesToUse) {
    if (!filesToUse?.length) return
    setOcrLoading(true)
    setError('')

    try {
      const formData = new FormData()
      filesToUse.forEach((file) => formData.append('file', file))

      const response = await fetch(`${ocrBase}/api/ocr`, {
        method: 'POST',
        body: formData,
      })

      const data = await readJson(response)
      const extracted = data?.text || ''
      setInputText(extracted)
      if (extracted.trim()) {
        await runPipeline(extracted, {
          replaceInput: true,
          callLlmOverride: false,
          suppressMessages: true,
        })
      }
    } catch (err) {
      setError(err.message || 'OCR failed.')
    } finally {
      setOcrLoading(false)
    }
  }

  function handleFileSelect(event) {
    const incoming = Array.from(event.target.files || [])
    if (!incoming.length) return
    setFiles(incoming)
    event.target.value = ''
    extractAndAnonymize(incoming)
  }

  function removeFile(index) {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  function handleReset() {
    setMessages([])
    setLastResult(null)
    setPiiCategories([])
    setSelectedLabels({})
    setDetectedPii({})
    setDriftPoints([])
    setError('')
    setInputText('')
    setInstructions('')
    setPromptBox('')
  }

  function handleApplyInstructions() {
    setError('')
    const base = lastResult?.anonymized_text || inputText
    if (!base.trim()) {
      setError('No anonymized text available. Run anonymization first.')
      return
    }
    const combined = instructions.trim()
      ? `${base}\n\n--- INSTRUCTIONS ---\n\n${instructions}\n\n--- END INSTRUCTIONS ---`
      : base
    setPromptBox(combined)
  }

  async function clearMappings() {
    if (!confirm('Clear all stored mappings? This cannot be undone.')) return
    setLoading(true)
    try {
      await fetch(`${apiBase}/api/clear-mappings`, { method: 'POST' }).then(readJson)
      await loadMappings()
    } catch (err) {
      setError(err.message || 'Failed to clear mappings')
    } finally {
      setLoading(false)
    }
  }

  async function loadMappings() {
    setMappingsLoading(true)
    try {
      const data = await fetch(`${apiBase}/api/mappings`).then(readJson)
      const entries = Object.entries(data?.mappings || {})
      setStoredMappings(entries)
    } catch {
      setStoredMappings([])
    } finally {
      setMappingsLoading(false)
    }
  }

  async function loadDriftHistory() {
    try {
      const data = await fetch(`${modelBase}/history?limit=120`).then(readJson)
      setDriftPoints(data?.points || [])
    } catch {
      setDriftPoints([])
    }
  }

  async function deleteMapping(key) {
    try {
      await fetch(`${apiBase}/api/delete-mapping`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      }).then(readJson)
      await loadMappings()
    } catch (err) {
      setError(err.message || 'Failed to delete mapping')
    }
  }

  async function refreshModelStatus() {
    try {
      const response = await fetch(`${modelBase}/model-status`)
      const data = await readJson(response)
      setModelStatus(data?.model_status || null)
      setLabelStats(data?.label_stats || null)
    } catch {
      setModelStatus(null)
    }
  }

  async function trainModel() {
    setTraining(true)
    setError('')
    try {
      await fetch(`${modelBase}/train-model`, { method: 'POST' }).then(readJson)
      await refreshModelStatus()
      await loadDriftHistory()
    } catch (err) {
      setError(err.message || 'Training failed')
    } finally {
      setTraining(false)
    }
  }

  const driftSeries = useMemo(() => {
    const points = windowedDrift
    const metric = (key) => points.map((p) => (Number.isFinite(p?.[key]) ? p[key] : null))

    const primaryRisk = [
      { label: 'Final Drift', values: metric('drift_score'), color: '#0ea5e9' },
      { label: 'High-Risk Prob', values: metric('high_risk_probability'), color: '#8b5cf6' },
    ]
    if (riskMode === 'all') {
      primaryRisk.push(
        { label: 'Anomaly', values: metric('anomaly_score'), color: '#ef4444' },
        { label: 'Confidence', values: metric('confidence_score'), color: '#22d3ee' }
      )
    }

    const nlp = [{ label: 'Semantic', values: metric('semantic_drift'), color: '#10b981' }]
    if (nlpMode === 'all') {
      nlp.push(
        { label: 'Sentiment', values: metric('sentiment_drift'), color: '#f97316' },
        { label: 'Lexical', values: metric('lexical_drift'), color: '#94a3b8' }
      )
    }

    const distribution = [
      { label: 'JS', values: metric('js_divergence'), color: '#22d3ee' },
      { label: 'MMD', values: metric('mmd_drift'), color: '#8b5cf6' },
    ]
    if (distributionMode === 'all') {
      distribution.push(
        { label: '1 - MMD p', values: metric('mmd_pvalue_inv'), color: '#f59e0b' },
        { label: 'Historical', values: metric('historical_drift'), color: '#64748b' },
        { label: 'Domain AUC', values: metric('domain_auc_shift'), color: '#10b981' }
      )
    }

    const time = [
      { label: 'Trend', values: metric('trend_shift'), color: '#e11d48' },
      { label: 'Page-Hinkley', values: metric('page_hinkley_score'), color: '#b45309' },
    ]
    if (timeMode === 'all') {
      time.push(
        { label: 'EWMA', values: metric('ewma_score'), color: '#334155' },
        { label: 'Volatility', values: metric('volatility_risk'), color: '#0ea5e9' }
      )
    }

    return { risk: primaryRisk, nlp, distribution, time }
  }, [windowedDrift, riskMode, nlpMode, distributionMode, timeMode])

  const modelSummary = useMemo(() => {
    if (!modelStatus) return 'Model status unavailable.'
    if (!modelStatus.available) return 'Model not trained yet.'
    const metrics = modelStatus.metrics
    if (!metrics) return 'Model available.'
    return `AUC ${formatNumber(metrics.roc_auc, 3)}, F1 ${formatNumber(metrics.f1, 3)} - ${metrics.samples || 0} samples.`
  }, [modelStatus])

  const labelStatusText = useMemo(() => {
    if (!labelStats) return 'Label readiness unavailable.'
    const total = Number(labelStats.labeled_total || 0)
    const manual = Number(labelStats.manual_labeled_total || 0)
    const auto = Math.max(0, total - manual)
    const positives = Number(labelStats.positives || 0)
    const negatives = Number(labelStats.negatives || 0)
    return `Training data: ${total} samples (manual ${manual}, auto ${auto}). Safe ${negatives}, Drift ${positives}.`
  }, [labelStats])

  function syncTextareaHeight() {
    if (!textareaRef.current) return
    const el = textareaRef.current
    el.style.height = 'auto'
    const maxHeight = 220
    const next = Math.min(el.scrollHeight, maxHeight)
    el.style.height = `${next}px`
    el.style.overflowY = el.scrollHeight > maxHeight ? 'auto' : 'hidden'
    if (highlightRef.current) {
      highlightRef.current.style.height = `${next}px`
    }
  }

  function handleTextareaScroll(event) {
    if (!highlightRef.current) return
    highlightRef.current.scrollTop = event.target.scrollTop
    highlightRef.current.scrollLeft = event.target.scrollLeft
  }
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">PII</div>
          <div>
            <div className="brand-title">DocSafe</div>
            <div className="brand-sub">Cybersecurity-grade privacy workspace</div>
          </div>
        </div>
        <div className="security-pill">Encrypted mappings - Zero-retention</div>
      </header>

      <main className="layout">
        <aside className="side left resizable">
          <div className="panel">
            <div className="panel-title">PII Overview</div>
            <PieChart data={piiCategories} />
          </div>

          <div className="panel">
            <div className="panel-title">PII Statistics</div>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Entities</div>
                <div className="stat-value">{totalEntities}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Categories</div>
                <div className="stat-value">{piiCategories.length}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Locked</div>
                <div className="stat-value">{lockedLabels.length}</div>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">PII Categories</div>
            <div className="pii-list">
              {piiCategories.length === 0 ? (
                <div className="chart-empty">No categories yet.</div>
              ) : (
                piiCategories.map((item) => (
                  <label key={item.label} className={`pii-row ${item.locked ? 'locked' : ''}`}>
                    <input
                      type="checkbox"
                      checked={item.locked ? true : Boolean(selectedLabels[item.label])}
                      disabled={item.locked}
                      onChange={(e) =>
                        setSelectedLabels((prev) => ({ ...prev, [item.label]: e.target.checked }))
                      }
                    />
                    <span>{item.label}</span>
                    <span className="pii-count">{item.count}</span>
                  </label>
                ))
              )}
            </div>
          </div>
        </aside>

        <section className="center">
          <section className="hero">
            <div>
              <div className="hero-title">Secure chat </div>
              <div className="hero-sub">Zero-trust anonymization before any model exposure.</div>
            </div>
            <div className="status">
              {loading || ocrLoading ? <span className="pulse">Processing...</span> : <span>Ready</span>}
            </div>
          </section>

          <section className="chat">
            <div className="chat-window">
              {messages.length === 0 ? (
                <div className="chat-empty">
                  <div className="chat-empty-title">Start a secure exchange</div>
                  <div className="chat-empty-body">
                    Upload a document or paste text to generate anonymized responses.
                  </div>
                </div>
              ) : (
                messages.map((message, index) => (
                  <div key={`${message.role}-${index}`} className={`bubble ${message.role}`}>
                    <div className="bubble-role">{message.role === 'user' ? 'You' : 'Assistant'}</div>
                    <div className="bubble-text">{message.content}</div>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="panel composer">
            <form onSubmit={handleSubmit} className="composer-form">
              <div className="composer-shell">
                <div className="composer-textarea">
                  <div
                    className="highlight-layer"
                    ref={highlightRef}
                    dangerouslySetInnerHTML={{ __html: highlightHtml }}
                  />
                  <textarea
                    ref={textareaRef}
                    value={inputText}
                    onChange={(e) => {
                      setInputText(e.target.value)
                      syncTextareaHeight()
                    }}
                    onScroll={handleTextareaScroll}
                    placeholder="Ask DocSafe..."
                    rows={2}
                  />
                </div>

                <div className="composer-controls">
                  <button
                    type="button"
                    className="composer-icon"
                    aria-label="Attach"
                    onClick={() => fileInputRef.current?.click()}
                  >
                    +
                  </button>
                  <input
                    ref={fileInputRef}
                    className="file-input"
                    type="file"
                    multiple
                    accept="image/*,.pdf"
                    onChange={handleFileSelect}
                  />

                  <select
                    className="mode-select"
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                    aria-label="Anonymization mode"
                  >
                    <option value="pseudonymize">Pseudonymize</option>
                    <option value="mask">Mask</option>
                    <option value="replace">Replace</option>
                  </select>

                  <button type="button" className="composer-anon" onClick={anonymizeOnly}>
                    Anonymize
                  </button>

                  <button
                    type="button"
                    className="composer-clear"
                    onClick={() => {
                      handleReset()
                      window.location.reload()
                    }}
                  >
                    Clear
                  </button>

                  <button className="composer-send" type="submit" aria-label="Send" disabled={loading}>
                    ^
                  </button>
                </div>
              </div>

              {files.length > 0 && (
                <div className="file-pill-group compact">
                  {files.map((file, idx) => (
                    <span key={`${file.name}-${idx}`} className="file-pill">
                      {file.name}
                      <button type="button" onClick={() => removeFile(idx)}>x</button>
                    </span>
                  ))}
                </div>
              )}
            </form>
          </section>

          <details className="panel">
            <summary className="panel-title">Advanced options</summary>
            <div className="advanced-grid">
              <div className="panel">
                <div className="panel-title">Scenario / Instructions</div>
                <textarea
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  placeholder="Optional context for the LLM"
                  rows={4}
                />
                <div className="button-row">
                  <button className="ghost" type="button" onClick={handleApplyInstructions}>
                    Apply
                  </button>
                  <button className="ghost" type="button" onClick={() => setInstructions('')}>
                    Clear
                  </button>
                </div>
              </div>

              <div className="panel">
                <div className="panel-title">Prompt preview</div>
                <textarea value={promptBox} readOnly rows={4} placeholder="Preview after apply" />
              </div>

              <div className="panel">
                <div className="panel-title">Actions</div>
                <div className="button-row">
                  <button type="button" className="ghost" onClick={clearMappings}>
                    Clear all mappings
                  </button>
                </div>
                <div className="mapping-list">
                  {mappingsLoading ? (
                    <div className="hint">Loading mappings...</div>
                  ) : storedMappings.length === 0 ? (
                    <div className="hint">No stored mappings.</div>
                  ) : (
                    storedMappings.map(([key, value]) => (
                      <div key={key} className="mapping-row">
                        <div className="mapping-key">{key}</div>
                        <div className="mapping-value">{value}</div>
                        <button type="button" onClick={() => deleteMapping(key)}>
                          Delete
                        </button>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </details>

          {error ? <div className="error">{error}</div> : null}

          <details className="panel">
            <summary className="panel-title">Outputs</summary>
            <div className="results">
              <div className="panel">
                <div className="panel-title">Anonymized Output</div>
                <div className="panel-body">
                  {lastResult?.anonymized_text ? lastResult.anonymized_text : 'No anonymized text yet.'}
                </div>
                <div className="panel-footer">
                  Mappings: {lastResult?.mappings_count ?? 0} - Mode: {lastResult?.mode || '-'}
                </div>
              </div>

              <div className="panel">
                <div className="panel-title">Model Response (Anonymized)</div>
                <div className="panel-body">
                  {lastResult?.llm_response_anonymized || 'Send to the assistant to populate.'}
                </div>
              </div>

              <div className="panel">
                <div className="panel-title">Deanonymized Reply</div>
                <div className="panel-body">
                  {lastResult?.deanonymized_output || 'No deanonymized reply yet.'}
                </div>
              </div>
            </div>
          </details>
        </section>
        <aside className="side right">
          <div className="panel">
            <div className="panel-title">Model Training</div>
            <div className="model-status">
              <div>{modelStatus?.available ? 'Model ready' : 'Model not trained yet'}</div>
              <div className="hint">{modelSummary}</div>
            </div>
            <div className="model-status">
              <div>Label readiness</div>
              <div className="hint">{labelStatusText}</div>
            </div>
            <button className="primary" type="button" onClick={trainModel} disabled={training}>
              {training ? 'Training...' : 'Train model'}
            </button>
          </div>

          <div className="panel">
            <div className="panel-title">PII Coverage</div>
            <BarChart data={piiCategories} />
          </div>

          <div className="panel">
            <div className="panel-title">Drift Controls</div>
            <div className="control-grid">
              <label>
                Window
                <select value={driftWindow} onChange={(e) => setDriftWindow(Number(e.target.value))}>
                  <option value={20}>20</option>
                  <option value={40}>40</option>
                  <option value={60}>60</option>
                  <option value={120}>120</option>
                </select>
              </label>
              <label>
                Risk
                <select value={riskMode} onChange={(e) => setRiskMode(e.target.value)}>
                  <option value="primary">Primary</option>
                  <option value="all">All</option>
                </select>
              </label>
              <label>
                NLP
                <select value={nlpMode} onChange={(e) => setNlpMode(e.target.value)}>
                  <option value="primary">Primary</option>
                  <option value="all">All</option>
                </select>
              </label>
              <label>
                Distribution
                <select value={distributionMode} onChange={(e) => setDistributionMode(e.target.value)}>
                  <option value="primary">Primary</option>
                  <option value="all">All</option>
                </select>
              </label>
              <label>
                Time
                <select value={timeMode} onChange={(e) => setTimeMode(e.target.value)}>
                  <option value="primary">Primary</option>
                  <option value="all">All</option>
                </select>
              </label>
            </div>
          </div>

          <div className="panel">
            <div className="panel-title">Drift Risk</div>
            <LineChart series={driftSeries.risk} />
          </div>

          <div className="panel">
            <div className="panel-title">NLP Drift</div>
            <LineChart series={driftSeries.nlp} />
          </div>

          <div className="panel">
            <div className="panel-title">Distribution Shift</div>
            <LineChart series={driftSeries.distribution} />
          </div>

          <div className="panel">
            <div className="panel-title">Temporal Drift</div>
            <LineChart series={driftSeries.time} />
          </div>

          <div className="panel">
            <div className="panel-title">Drift Signals</div>
            <div className="signal-grid">
              {(driftSummary || METRICS).map((metric) => (
                <div key={metric.key} className="signal">
                  <div className="signal-label">{metric.label}</div>
                  <div className="signal-value">{driftSummary ? formatNumber(metric.value) : '-'}</div>
                </div>
              ))}
            </div>
            <div className="panel-footer">
              {lastResult?.drift_available ? 'Drift engine enabled.' : 'Drift engine unavailable.'}
            </div>
          </div>
        </aside>
      </main>
    </div>
  )
}

export default App

