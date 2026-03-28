import { useEffect, useState } from 'react'
import FHIR from 'fhirclient'
import SepsisChecklist from './components/SepsisChecklist'
import './App.css'

async function fetchBundles() {
  // Mode 1: CDS Hooks direct launch (fhirServiceUrl + patientId in sessionStorage)
  const fhirServiceUrl = sessionStorage.getItem('fhirServiceUrl')
  const patientId = sessionStorage.getItem('patientId')

  if (fhirServiceUrl && patientId) {
    const base = fhirServiceUrl.replace(/\/$/, '')
    const headers = { Accept: 'application/fhir+json' }
    const [vRes, lRes] = await Promise.all([
      fetch(`${base}/Observation?patient=${patientId}&category=vital-signs&_sort=-date&_count=10`, { headers }),
      fetch(`${base}/Observation?patient=${patientId}&category=laboratory&_sort=-date&_count=20`, { headers }),
    ])
    const vBundle = await vRes.json()
    const lBundle = lRes.ok ? await lRes.json() : { entry: [] }
    return { vBundle, lBundle }
  }

  // Mode 2: Full SMART OAuth launch
  const client = await FHIR.oauth2.ready()
  const pid = client.patient.id
  const [vBundle, lBundle] = await Promise.all([
    client.request(`Observation?patient=${pid}&category=vital-signs&_sort=-date&_count=10`),
    client.request(`Observation?patient=${pid}&category=laboratory&_sort=-date&_count=20`).catch(() => ({ entry: [] })),
  ])
  return { vBundle, lBundle }
}

export default function App() {
  const [state, setState] = useState({ status: 'loading', vitals: null, labs: null, error: null })

  useEffect(() => {
    fetchBundles()
      .then(({ vBundle, lBundle }) => setState({ status: 'ready', vitals: vBundle, labs: lBundle, error: null }))
      .catch(err => setState({ status: 'error', vitals: null, labs: null, error: err.message }))
  }, [])

  if (state.status === 'loading') {
    return (
      <div className="app-shell">
        <header className="app-header">
          <span className="app-logo">Clin<span className="app-logo-dot">Agent</span></span>
          <span className="app-subtitle">Sepsis Early Warning</span>
        </header>
        <div className="loading">Loading patient data…</div>
      </div>
    )
  }

  if (state.status === 'error') {
    return (
      <div className="app-shell">
        <header className="app-header">
          <span className="app-logo">Clin<span className="app-logo-dot">Agent</span></span>
        </header>
        <div className="error-box">
          <strong>Unable to load patient data.</strong>
          <p>{state.error}</p>
          <p className="hint">
            Launch this app via a CDS Hooks app-link card or directly from an EHR SMART launch.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-logo">Clin<span className="app-logo-dot">Agent</span></span>
        <span className="app-subtitle">Sepsis Early Warning</span>
      </header>
      <main>
        <SepsisChecklist vitalsBundle={state.vitals} labsBundle={state.labs} />
      </main>
    </div>
  )
}
