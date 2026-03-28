import FHIR from 'fhirclient'

// SMART launch entry point.
// The EHR redirects here with ?launch=<token>&iss=<fhir-server-url>
// We immediately redirect to the EHR's authorization endpoint.
FHIR.oauth2.authorize({
  clientId: 'clinagent-sepsis',
  scope: 'patient/Observation.read patient/Patient.read launch/patient openid fhirUser',
  redirectUri: './index.html',
})
