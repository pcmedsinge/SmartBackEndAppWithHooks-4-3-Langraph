import { useEffect, useState } from 'react'
import FHIR from 'fhirclient'
import SepsisChecklist from './components/SepsisChecklist'
import './App.css'

export default function App() {
  const [state, setState] = useState({ status: 'loading', vitals: null, labs: null, error: null })

  useEffect(() => {
    FHIR.oauth2
      .ready()
      .then(async (client) => {
        const patientId = client.patient.id

        // Fetch vitals and labs in parallel
        const [vBundle, lBundle] = await Promise.all([
          client.request(
            `Observation?patient=${patientId}&category=vital-signs&_sort=-date&_count=10`
          ),
          client.request(
            `Observation?patient=${patientId}&category=laboratory&_sort=-date&_count=20`
          ).catch(() => ({ entry: [] })),
        ])

        setState({ status: 'ready', vitals: vBundle, labs: lBundle, error: null })
      })
      .catch((err) => {
        setState({ status: 'error', vitals: null, labs: null, error: err.message })
      })
  }, [])

  if (state.status === 'loading') {
    return (
      <div className="app-shell">
        <header className="app-header">
          <span className="app-logo">ClinAgent</span>
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
          <span className="app-logo">ClinAgent</span>
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
        <span className="app-logo">ClinAgent</span>
        <span className="app-subtitle">Sepsis Early Warning</span>
      </header>
      <main>
        <SepsisChecklist vitalsBundle={state.vitals} labsBundle={state.labs} />
      </main>
    </div>
  )
}
