/**
 * SepsisChecklist — displays qSOFA score and Sepsis-3 checklist.
 * Read-only in Phase 1. All logic mirrors the Python sepsis tools.
 */

const LOINC_RR    = '9279-1'
const LOINC_SBP   = '8480-6'
const LOINC_BP_PANEL = '55284-4'
const LOINC_GCS   = '9269-2'
const LOINC_LACTATE   = '2524-7'
const LOINC_LACTATE_ALT = '59032-3'
const LOINC_WBC   = '6690-2'

function getLoinc(obs) {
  return (obs.code?.coding ?? [])
    .filter(c => c.system?.toLowerCase().includes('loinc'))
    .map(c => c.code)
}

function getNumericValue(obs) {
  if (obs.valueQuantity?.value != null) return parseFloat(obs.valueQuantity.value)
  // component-based (BP panel)
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
    if (codes.includes(LOINC_RR) && vitals.rr == null)       vitals.rr  = getNumericValue(obs)
    if (codes.includes(LOINC_SBP) && vitals.sbp == null)     vitals.sbp = getNumericValue(obs)
    if (codes.includes(LOINC_BP_PANEL) && vitals.sbp == null) vitals.sbp = getComponentValue(obs, LOINC_SBP)
    if (codes.includes(LOINC_GCS) && vitals.gcs == null)     vitals.gcs = getNumericValue(obs)
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
  if (vitals.rr != null && vitals.rr >= 22)  { score++; criteria.push({ label: `Respiratory rate ${vitals.rr} breaths/min`, threshold: '≥ 22', met: true }) }
  else criteria.push({ label: `Respiratory rate ${vitals.rr != null ? vitals.rr : '—'} breaths/min`, threshold: '≥ 22', met: false })

  if (vitals.sbp != null && vitals.sbp <= 100) { score++; criteria.push({ label: `Systolic BP ${vitals.sbp} mmHg`, threshold: '≤ 100', met: true }) }
  else criteria.push({ label: `Systolic BP ${vitals.sbp != null ? vitals.sbp : '—'} mmHg`, threshold: '≤ 100', met: false })

  if (vitals.gcs != null && vitals.gcs < 15)  { score++; criteria.push({ label: `GCS ${vitals.gcs}`, threshold: '< 15', met: true }) }
  else criteria.push({ label: `GCS ${vitals.gcs != null ? vitals.gcs : '—'}`, threshold: '< 15', met: false })

  return { score, criteria }
}

function riskLevel(score) {
  if (score >= 2) return 'high'
  if (score === 1) return 'moderate'
  return 'low'
}

const RISK_COLORS = { high: '#c0392b', moderate: '#e67e22', low: '#27ae60' }
const RISK_LABELS = { high: 'HIGH RISK', moderate: 'MODERATE RISK', low: 'LOW RISK' }

const SEPSIS3_CHECKLIST = [
  'Obtain blood cultures (2 sets) before antibiotics',
  'Administer broad-spectrum antibiotics within 1 hour',
  'Measure lactate — repeat if initial lactate > 2 mmol/L',
  'Begin 30 mL/kg IV crystalloid for hypotension or lactate ≥ 4 mmol/L',
  'Apply vasopressors if MAP < 65 mmHg despite fluid resuscitation',
  'Monitor urine output (target ≥ 0.5 mL/kg/hr)',
  'Reassess fluid status and tissue perfusion within 1–2 hours',
]

export default function SepsisChecklist({ vitalsBundle, labsBundle }) {
  const vitals = extractVitals(vitalsBundle)
  const labs   = extractLabs(labsBundle)
  const { score, criteria } = scoreQsofa(vitals)
  const risk = riskLevel(score)
  const color = RISK_COLORS[risk]

  return (
    <div className="checklist-card">

      {/* qSOFA Score */}
      <section className="qsofa-section">
        <div className="qsofa-score-box" style={{ borderColor: color }}>
          <div className="qsofa-label">qSOFA Score</div>
          <div className="qsofa-number" style={{ color }}>{score} / 3</div>
          <div className="qsofa-risk" style={{ backgroundColor: color }}>{RISK_LABELS[risk]}</div>
        </div>

        <div className="qsofa-criteria">
          {criteria.map((c, i) => (
            <div key={i} className={`criterion ${c.met ? 'met' : 'not-met'}`}>
              <span className="criterion-icon">{c.met ? '✓' : '○'}</span>
              <span className="criterion-text">
                <strong>{c.label}</strong>
                <span className="criterion-threshold">threshold: {c.threshold}</span>
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Supporting Labs */}
      <section className="labs-section">
        <h3>Supporting Labs</h3>
        <div className="lab-row">
          <span className="lab-name">Lactate</span>
          <span className={`lab-value ${labs.lactate != null && labs.lactate >= 2 ? 'abnormal' : ''}`}>
            {labs.lactate != null ? `${labs.lactate} mmol/L` : '—'}
          </span>
          {labs.lactate != null && labs.lactate >= 4 && <span className="lab-flag critical-flag">CRITICAL ≥ 4</span>}
          {labs.lactate != null && labs.lactate >= 2 && labs.lactate < 4 && <span className="lab-flag warn-flag">ELEVATED ≥ 2</span>}
        </div>
        <div className="lab-row">
          <span className="lab-name">WBC</span>
          <span className={`lab-value ${labs.wbc != null && (labs.wbc > 12 || labs.wbc < 4) ? 'abnormal' : ''}`}>
            {labs.wbc != null ? `${labs.wbc} ×10³/µL` : '—'}
          </span>
          {labs.wbc != null && (labs.wbc > 12 || labs.wbc < 4) && <span className="lab-flag warn-flag">ABNORMAL</span>}
        </div>
      </section>

      {/* Sepsis-3 Checklist */}
      {risk !== 'low' && (
        <section className="sepsis3-section">
          <h3>Sepsis-3 Hourly Bundle</h3>
          <p className="sepsis3-note">Read-only checklist — complete actions in EHR</p>
          <ul className="sepsis3-list">
            {SEPSIS3_CHECKLIST.map((item, i) => (
              <li key={i} className="sepsis3-item">
                <span className="sepsis3-check">□</span>
                {item}
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="app-footer">
        Powered by ClinAgent · qSOFA per Singer et al., JAMA 2016 · Read-only
      </footer>
    </div>
  )
}
