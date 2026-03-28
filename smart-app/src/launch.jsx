import FHIR from 'fhirclient'

// SMART launch entry point.
// Two modes:
//   1. Full SMART launch from EHR  — ?launch=<token>&iss=<url>  → OAuth flow
//   2. CDS Hooks app-link launch   — ?fhirServiceUrl=<url>&patientId=<id> → skip OAuth, go direct
const params = new URLSearchParams(window.location.search)
const fhirServiceUrl = params.get('fhirServiceUrl')
const patientId = params.get('patientId')

if (fhirServiceUrl && patientId) {
  // CDS Hooks sandbox passes fhirServiceUrl + patientId directly — no OAuth needed
  sessionStorage.setItem('fhirServiceUrl', fhirServiceUrl)
  sessionStorage.setItem('patientId', patientId)
  window.location.href = './index.html'
} else {
  // Full SMART EHR launch — go through OAuth
  FHIR.oauth2.authorize({
    clientId: 'clinagent-sepsis',
    scope: 'patient/Observation.read patient/Patient.read launch/patient openid fhirUser',
    redirectUri: './index.html',
  })
}
