/**
 * SepsisChecklist — qSOFA scoring, Sepsis-3 bundle, and provider action panel.
 * Mirrors Python sepsis tools logic exactly.
 */
import { useState } from 'react'

const LOINC_RR          = '9279-1'
const LOINC_SBP         = '8480-6'
const LOINC_BP_PANEL    = '55284-4'
const LOINC_BP_PANEL_ALT = '85354-9'   // Synthea / US Core variant
const LOINC_GCS         = '9269-2'
const LOINC_LACTATE     = '2524-7'
const LOINC_LACTATE_ALT = '59032-3'
const LOINC_WBC         = '6690-2'

function getLoinc(obs) {
  return (obs.code?.coding ?? [])
    .filter(c => c.system?.toLowerCase().includes('loinc'))
    .map(c => c.code)
}

function getNumericValue(obs) {
  if (obs.valueQuantity?.value != null) return parseFloat(obs.valueQuantity.value)
  for (const comp of obs.component ?? []) {
    if (comp.valueQuantity?.value != null) return parseFloat(comp.valueQuantity.value)
  }
  return null
}

function getComponentValue(obs, loincCode) {
  for (const comp of obs.component ?? []) {
    const codes = (comp.code?.coding ?? []).map(c => c.code)
    if (codes.includes(loincCode) && comp.valueQuantity?.value != null)
      return parseFloat(comp.valueQuantity.value)
  }
  return null
}

function extractVitals(bundle) {
  const vitals = { rr: null, sbp: null, gcs: null }
  for (const entry of bundle?.entry ?? []) {
    const obs = entry.resource
    if (obs?.resourceType !== 'Observation') continue
    if (['cancelled', 'entered-in-error'].includes(obs.status)) continue
    const codes = getLoinc(obs)
    if (codes.includes(LOINC_RR) && vitals.rr == null)
      vitals.rr = getNumericValue(obs)
    if (codes.includes(LOINC_SBP) && vitals.sbp == null)
      vitals.sbp = getNumericValue(obs)
    if ((codes.includes(LOINC_BP_PANEL) || codes.includes(LOINC_BP_PANEL_ALT)) && vitals.sbp == null)
      vitals.sbp = getComponentValue(obs, LOINC_SBP)
    if (codes.includes(LOINC_GCS) && vitals.gcs == null)
      vitals.gcs = getNumericValue(obs)
  }
  return vitals
}

function extractLabs(bundle) {
  const labs = { lactate: null, wbc: null }
  for (const entry of bundle?.entry ?? []) {
    const obs = entry.resource
    if (obs?.resourceType !== 'Observation') continue
    if (['cancelled', 'entered-in-error'].includes(obs.status)) continue
    const codes = getLoinc(obs)
    if ((codes.includes(LOINC_LACTATE) || codes.includes(LOINC_LACTATE_ALT)) && labs.lactate == null)
      labs.lactate = getNumericValue(obs)
    if (codes.includes(LOINC_WBC) && labs.wbc == null)
      labs.wbc = getNumericValue(obs)
  }
  return labs
}

function scoreQsofa(vitals) {
  const criteria = []
  let score = 0
  if (vitals.rr != null && vitals.rr >= 22) {
    score++
    criteria.push({ key: 'rr', label: 'Respiratory Rate', value: `${vitals.rr} /min`, threshold: '\u226522', met: true, icon: '🫁' })
  } else {
    criteria.push({ key: 'rr', label: 'Respiratory Rate', value: vitals.rr != null ? `${vitals.rr} /min` : '\u2014', threshold: '\u226522', met: false, icon: '🫁' })
  }
  if (vitals.sbp != null && vitals.sbp <= 100) {
    score++
    criteria.push({ key: 'sbp', label: 'Systolic BP', value: `${vitals.sbp} mmHg`, threshold: '\u2264100', met: true, icon: '❤️' })
  } else {
    criteria.push({ key: 'sbp', label: 'Systolic BP', value: vitals.sbp != null ? `${vitals.sbp} mmHg` : '\u2014', threshold: '\u2264100', met: false, icon: '❤️' })
  }
  if (vitals.gcs != null && vitals.gcs < 15) {
    score++
    criteria.push({ key: 'gcs', label: 'Mental Status (GCS)', value: `GCS ${vitals.gcs}`, threshold: '<15', met: true, icon: '🧠' })
  } else {
    criteria.push({ key: 'gcs', label: 'Mental Status (GCS)', value: vitals.gcs != null ? `GCS ${vitals.gcs}` : '\u2014', threshold: '<15', met: false, icon: '🧠' })
  }
  return { score, criteria }
}

function riskLevel(score) {
  if (score >= 2) return 'high'
  if (score === 1) return 'moderate'
  return 'low'
}

const RISK_CONFIG = {
  high:     { color: '#dc2626', bg: '#fef2f2', border: '#fca5a5', badge: '#dc2626', label: 'HIGH RISK',     emoji: '🔴', message: 'Immediate sepsis protocol indicated' },
  moderate: { color: '#d97706', bg: '#fffbeb', border: '#fcd34d', badge: '#d97706', label: 'MODERATE RISK', emoji: '🟡', message: 'Monitor closely — reassess within 1 hour' },
  low:      { color: '#16a34a', bg: '#f0fdf4', border: '#86efac', badge: '#16a34a', label: 'LOW RISK',      emoji: '🟢', message: 'No immediate sepsis concern' },
}

const BUNDLE_ACTIONS = [
  { id: 'cultures',    time: '0 min',  icon: '🧫', label: 'Blood Cultures',         detail: '2 sets before antibiotics',                    urgent: true  },
  { id: 'abx',         time: '60 min', icon: '💊', label: 'Broad-spectrum Antibiotics', detail: 'Administer within 1 hour of sepsis recognition', urgent: true  },
  { id: 'lactate',     time: '0 min',  icon: '🔬', label: 'Lactate Level',           detail: 'Repeat if initial lactate > 2 mmol/L',          urgent: true  },
  { id: 'fluids',      time: '30 min', icon: '💧', label: 'IV Crystalloid 30 mL/kg', detail: 'For hypotension or lactate \u2265 4 mmol/L',    urgent: true  },
  { id: 'vasopressors',time: '60 min', icon: '💉', label: 'Vasopressors if needed',  detail: 'Target MAP \u2265 65 mmHg',                     urgent: false },
  { id: 'urine',       time: 'ongoing',icon: '📊', label: 'Urine Output Monitoring', detail: 'Target \u2265 0.5 mL/kg/hr',                   urgent: false },
  { id: 'reassess',    time: '1-2 hr', icon: '🔄', label: 'Reassess Perfusion',      detail: 'Fluid status and tissue perfusion',              urgent: false },
]

const QUICK_ACTIONS = [
  { icon: '📞', label: 'Notify Rapid Response', color: '#dc2626' },
  { icon: '🏥', label: 'ICU Consult',           color: '#7c3aed' },
  { icon: '📋', label: 'Sepsis Order Set',       color: '#0284c7' },
  { icon: '📝', label: 'Document Assessment',    color: '#059669' },
]

export default function SepsisChecklist({ vitalsBundle, labsBundle }) {
  const vitals = extractVitals(vitalsBundle)
  const labs   = extractLabs(labsBundle)
  const { score, criteria } = scoreQsofa(vitals)
  const risk   = riskLevel(score)
  const cfg    = RISK_CONFIG[risk]

  const [checked, setChecked] = useState({})
  const [activeTab, setActiveTab] = useState('checklist')

  const toggle = (id) => setChecked(prev => ({ ...prev, [id]: !prev[id] }))
  const completedCount = Object.values(checked).filter(Boolean).length

  return (
    <div className="sc-shell">

      {/* Risk Banner */}
      <div className="sc-banner" style={{ background: cfg.bg, borderColor: cfg.border }}>
        <div className="sc-banner-left">
          <span className="sc-risk-emoji">{cfg.emoji}</span>
          <div>
            <div className="sc-risk-label" style={{ color: cfg.color }}>{cfg.label}</div>
            <div className="sc-risk-msg">{cfg.message}</div>
          </div>
        </div>
        <div className="sc-score-pill" style={{ background: cfg.badge }}>
          <span className="sc-score-num">{score}</span>
          <span className="sc-score-den">/3</span>
          <span className="sc-score-tag">qSOFA</span>
        </div>
      </div>

      {/* qSOFA Criteria */}
      <div className="sc-section">
        <div className="sc-section-title">qSOFA Criteria</div>
        <div className="sc-criteria-grid">
          {criteria.map(c => (
            <div key={c.key} className={`sc-criterion ${c.met ? 'met' : 'unmet'}`} style={c.met ? { borderColor: cfg.color } : {}}>
              <div className="sc-crit-icon">{c.icon}</div>
              <div className="sc-crit-body">
                <div className="sc-crit-label">{c.label}</div>
                <div className="sc-crit-value" style={c.met ? { color: cfg.color } : {}}>{c.value}</div>
                <div className="sc-crit-thresh">Threshold: {c.threshold}</div>
              </div>
              <div className={`sc-crit-badge ${c.met ? 'met' : 'unmet'}`} style={c.met ? { background: cfg.color } : {}}>
                {c.met ? '✓' : '—'}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Supporting Labs */}
      <div className="sc-section">
        <div className="sc-section-title">Supporting Labs</div>
        <div className="sc-labs-row">
          <div className={`sc-lab-card ${labs.lactate != null && labs.lactate >= 2 ? 'abnormal' : ''}`}>
            <div className="sc-lab-icon">🔬</div>
            <div className="sc-lab-name">Lactate</div>
            <div className="sc-lab-val">{labs.lactate != null ? `${labs.lactate} mmol/L` : '—'}</div>
            {labs.lactate != null && labs.lactate >= 4 && <div className="sc-lab-flag critical">CRITICAL ≥4</div>}
            {labs.lactate != null && labs.lactate >= 2 && labs.lactate < 4 && <div className="sc-lab-flag warn">ELEVATED ≥2</div>}
            {(labs.lactate == null || labs.lactate < 2) && <div className="sc-lab-flag normal">NORMAL</div>}
          </div>
          <div className={`sc-lab-card ${labs.wbc != null && (labs.wbc > 12 || labs.wbc < 4) ? 'abnormal' : ''}`}>
            <div className="sc-lab-icon">🩸</div>
            <div className="sc-lab-name">WBC</div>
            <div className="sc-lab-val">{labs.wbc != null ? `${labs.wbc} \u00d710\u00b3/\u00b5L` : '—'}</div>
            {labs.wbc != null && (labs.wbc > 12 || labs.wbc < 4) && <div className="sc-lab-flag warn">ABNORMAL</div>}
            {(labs.wbc == null || (labs.wbc >= 4 && labs.wbc <= 12)) && <div className="sc-lab-flag normal">NORMAL</div>}
          </div>
        </div>
      </div>

      {/* Tabs — only show for risk ≥ moderate */}
      {risk !== 'low' && (
        <div className="sc-section sc-section-tabs">
          <div className="sc-tabs">
            <button className={`sc-tab ${activeTab === 'checklist' ? 'active' : ''}`} onClick={() => setActiveTab('checklist')}>
              📋 Sepsis Bundle
              {completedCount > 0 && <span className="sc-tab-badge">{completedCount}/{BUNDLE_ACTIONS.length}</span>}
            </button>
            <button className={`sc-tab ${activeTab === 'actions' ? 'active' : ''}`} onClick={() => setActiveTab('actions')}>
              ⚡ Quick Actions
            </button>
            <button className={`sc-tab ${activeTab === 'timeline' ? 'active' : ''}`} onClick={() => setActiveTab('timeline')}>
              🕐 Timeline
            </button>
          </div>

          {/* Sepsis Bundle Tab */}
          {activeTab === 'checklist' && (
            <div className="sc-checklist">
              <div className="sc-checklist-header">
                <span>Sepsis-3 One-Hour Bundle</span>
                <span className="sc-progress">{completedCount}/{BUNDLE_ACTIONS.length} completed</span>
              </div>
              <div className="sc-progress-bar">
                <div className="sc-progress-fill" style={{ width: `${(completedCount / BUNDLE_ACTIONS.length) * 100}%`, background: cfg.color }} />
              </div>
              {BUNDLE_ACTIONS.map(action => (
                <label key={action.id} className={`sc-action-row ${checked[action.id] ? 'done' : ''} ${action.urgent ? 'urgent' : ''}`}>
                  <input type="checkbox" checked={!!checked[action.id]} onChange={() => toggle(action.id)} className="sc-checkbox" />
                  <span className="sc-action-icon">{action.icon}</span>
                  <div className="sc-action-body">
                    <div className="sc-action-label">{action.label}</div>
                    <div className="sc-action-detail">{action.detail}</div>
                  </div>
                  <span className="sc-action-time">{action.time}</span>
                </label>
              ))}
            </div>
          )}

          {/* Quick Actions Tab */}
          {activeTab === 'actions' && (
            <div className="sc-quick-actions">
              <p className="sc-actions-note">Tap to acknowledge — actions are completed in EHR</p>
              {QUICK_ACTIONS.map((a, i) => (
                <button key={i} className="sc-quick-btn" style={{ borderColor: a.color, color: a.color }}
                  onClick={() => alert(`Action logged: ${a.label}\nComplete this action in your EHR system.`)}>
                  <span>{a.icon}</span>
                  <span>{a.label}</span>
                  <span className="sc-quick-arrow">→</span>
                </button>
              ))}
              <div className="sc-actions-note" style={{ marginTop: 16 }}>
                For escalation: call Rapid Response Team or escalate to ICU attending.
              </div>
            </div>
          )}

          {/* Timeline Tab */}
          {activeTab === 'timeline' && (
            <div className="sc-timeline">
              <div className="sc-tl-title">Recommended Response Timeline</div>
              {[
                { time: 'T+0 min',  color: '#dc2626', items: ['Blood cultures ×2', 'Lactate level', 'Notify care team'] },
                { time: 'T+30 min', color: '#d97706', items: ['IV crystalloid 30 mL/kg', 'Urine catheter + output monitoring'] },
                { time: 'T+60 min', color: '#7c3aed', items: ['Broad-spectrum antibiotics', 'Vasopressors if MAP <65 mmHg'] },
                { time: 'T+1-3 hr', color: '#0284c7', items: ['Reassess fluid status', 'Repeat lactate if initial >2', 'ICU evaluation if deteriorating'] },
              ].map((block, i) => (
                <div key={i} className="sc-tl-block">
                  <div className="sc-tl-time" style={{ color: block.color, borderColor: block.color }}>{block.time}</div>
                  <div className="sc-tl-items">
                    {block.items.map((item, j) => (
                      <div key={j} className="sc-tl-item">
                        <span className="sc-tl-dot" style={{ background: block.color }} />
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Footer */}
      <footer className="sc-footer">
        <span>ClinAgent · qSOFA: Singer et al., JAMA 2016</span>
        <span>For clinical decision support only — not a substitute for clinical judgement</span>
      </footer>
    </div>
  )
}
