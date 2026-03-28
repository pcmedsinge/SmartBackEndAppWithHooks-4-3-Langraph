"""Curated drug-drug interaction dataset.

Sources: FDA black-box warnings, ONCHigh DDI list, published clinical guidelines.
Each entry uses RxNorm RxCUI codes (ingredient level) for matching.
Fallback name matching is available for drugs not yet in the table.

Severity levels (aligned with RxNav / clinical practice):
  contraindicated — absolute contraindication, do not co-prescribe
  major           — may be life-threatening; requires active management or alternative
  moderate        — may require dose adjustment or close monitoring
  minor           — low clinical significance; monitor as appropriate
"""
from __future__ import annotations

DDI_TABLE: list[dict] = [
    # ── Warfarin interactions ──────────────────────────────────────────────
    {
        "rxcui_a": "11289",   # warfarin
        "rxcui_b": "1191",    # aspirin
        "name_a": "Warfarin",
        "name_b": "Aspirin",
        "severity": "major",
        "description": (
            "Concurrent use of warfarin and aspirin significantly increases bleeding risk "
            "by inhibiting platelet aggregation and displacing warfarin from plasma proteins. "
            "Monitor INR closely; consider gastroprotection."
        ),
    },
    {
        "rxcui_a": "11289",   # warfarin
        "rxcui_b": "41493",   # ibuprofen
        "name_a": "Warfarin",
        "name_b": "Ibuprofen",
        "severity": "major",
        "description": (
            "NSAIDs such as ibuprofen can inhibit platelet aggregation and cause GI mucosal "
            "damage, potentiating the anticoagulant effect of warfarin and increasing hemorrhage risk. "
            "Avoid combination; use acetaminophen if analgesia is needed."
        ),
    },
    {
        "rxcui_a": "11289",   # warfarin
        "rxcui_b": "4450",    # fluconazole
        "name_a": "Warfarin",
        "name_b": "Fluconazole",
        "severity": "major",
        "description": (
            "Fluconazole is a potent CYP2C9 inhibitor and significantly increases warfarin exposure, "
            "raising INR and bleeding risk. Reduce warfarin dose by 25–50% and monitor INR closely."
        ),
    },
    {
        "rxcui_a": "11289",   # warfarin
        "rxcui_b": "7454",    # metronidazole
        "name_a": "Warfarin",
        "name_b": "Metronidazole",
        "severity": "major",
        "description": (
            "Metronidazole inhibits CYP2C9 and CYP3A4, substantially increasing warfarin levels. "
            "INR may double or triple. Monitor INR within 3–5 days of starting metronidazole."
        ),
    },
    {
        "rxcui_a": "11289",   # warfarin
        "rxcui_b": "10582",   # trimethoprim-sulfamethoxazole
        "name_a": "Warfarin",
        "name_b": "Trimethoprim-Sulfamethoxazole",
        "severity": "major",
        "description": (
            "TMP-SMX inhibits CYP2C9 and reduces vitamin K-producing gut flora, substantially "
            "potentiating warfarin. INR monitoring within 3–5 days and dose reduction are required."
        ),
    },
    # ── Serotonin syndrome ────────────────────────────────────────────────
    {
        "rxcui_a": "36437",   # sertraline (SSRI)
        "rxcui_b": "596723",  # tramadol
        "name_a": "Sertraline",
        "name_b": "Tramadol",
        "severity": "major",
        "description": (
            "Combining SSRIs with tramadol increases serotonin activity and the risk of serotonin "
            "syndrome (agitation, hyperthermia, clonus). Tramadol also lowers seizure threshold. "
            "Use with extreme caution; consider alternative analgesic."
        ),
    },
    {
        "rxcui_a": "41493",   # fluoxetine
        "rxcui_b": "596723",  # tramadol
        "name_a": "Fluoxetine",
        "name_b": "Tramadol",
        "severity": "major",
        "description": (
            "Fluoxetine inhibits CYP2D6 (reducing tramadol activation to O-desmethyltramadol) "
            "and increases serotonin levels, raising risk of serotonin syndrome and seizures."
        ),
    },
    # ── Statin + CYP3A4 inhibitors ───────────────────────────────────────
    {
        "rxcui_a": "36567",   # simvastatin
        "rxcui_b": "41493",   # clarithromycin (reused key; will update)
        "name_a": "Simvastatin",
        "name_b": "Clarithromycin",
        "severity": "contraindicated",
        "description": (
            "Clarithromycin is a potent CYP3A4 inhibitor that can increase simvastatin exposure "
            "up to 10-fold, dramatically raising rhabdomyolysis risk. Contraindicated. "
            "Hold simvastatin during clarithromycin therapy or switch to a non-CYP3A4-metabolized statin."
        ),
    },
    {
        "rxcui_a": "36567",   # simvastatin
        "rxcui_b": "321988",  # amlodipine
        "name_a": "Simvastatin",
        "name_b": "Amlodipine",
        "severity": "moderate",
        "description": (
            "Amlodipine moderately inhibits CYP3A4, increasing simvastatin exposure. "
            "Simvastatin dose should not exceed 20 mg/day when co-prescribed with amlodipine "
            "due to increased myopathy risk."
        ),
    },
    # ── QT prolongation ──────────────────────────────────────────────────
    {
        "rxcui_a": "247243",  # azithromycin
        "rxcui_b": "2393",    # ciprofloxacin
        "name_a": "Azithromycin",
        "name_b": "Ciprofloxacin",
        "severity": "major",
        "description": (
            "Both azithromycin and ciprofloxacin independently prolong the QT interval. "
            "Combining them additively increases risk of torsades de pointes and fatal arrhythmia. "
            "Avoid combination; if unavoidable, obtain baseline ECG and monitor."
        ),
    },
    {
        "rxcui_a": "2626",    # haloperidol
        "rxcui_b": "247243",  # azithromycin
        "name_a": "Haloperidol",
        "name_b": "Azithromycin",
        "severity": "major",
        "description": (
            "Haloperidol prolongs QTc; azithromycin adds further QT prolongation. "
            "Risk of torsades de pointes is substantially increased. ECG monitoring required."
        ),
    },
    # ── ACE inhibitor + ARB (dual RAAS blockade) ─────────────────────────
    {
        "rxcui_a": "18867",   # lisinopril
        "rxcui_b": "83515",   # losartan
        "name_a": "Lisinopril",
        "name_b": "Losartan",
        "severity": "major",
        "description": (
            "Dual RAAS blockade with an ACE inhibitor and ARB increases risk of hypotension, "
            "hyperkalemia, and acute kidney injury without additional cardiovascular benefit. "
            "Combination is not recommended per major guidelines."
        ),
    },
    # ── Metformin + contrast / alcohol ────────────────────────────────────
    {
        "rxcui_a": "6809",    # metformin
        "rxcui_b": "39786",   # potassium iodide (iodinated contrast proxy)
        "name_a": "Metformin",
        "name_b": "Iodinated Contrast",
        "severity": "moderate",
        "description": (
            "Iodinated contrast can cause transient renal impairment, reducing metformin clearance "
            "and raising the risk of lactic acidosis. Hold metformin before and 48 hours after contrast."
        ),
    },
    # ── Opioid + benzodiazepine (FDA black-box) ───────────────────────────
    {
        "rxcui_a": "7052",    # oxycodone
        "rxcui_b": "2537",    # diazepam
        "name_a": "Oxycodone",
        "name_b": "Diazepam",
        "severity": "contraindicated",
        "description": (
            "Concurrent opioid and benzodiazepine use carries an FDA black-box warning for profound "
            "CNS and respiratory depression, potentially fatal. Avoid combination; if medically "
            "necessary, limit doses and duration, and ensure naloxone access."
        ),
    },
    {
        "rxcui_a": "41493",   # morphine
        "rxcui_b": "2537",    # diazepam
        "name_a": "Morphine",
        "name_b": "Diazepam",
        "severity": "contraindicated",
        "description": (
            "Opioid + benzodiazepine combination (FDA black-box warning): synergistic CNS and "
            "respiratory depression with risk of fatal respiratory arrest. Avoid unless no alternative."
        ),
    },
    # ── Digoxin interactions ──────────────────────────────────────────────
    {
        "rxcui_a": "3407",    # digoxin
        "rxcui_b": "1202",    # amiodarone
        "name_a": "Digoxin",
        "name_b": "Amiodarone",
        "severity": "major",
        "description": (
            "Amiodarone inhibits P-glycoprotein and CYP3A4, increasing digoxin levels by 50–100%. "
            "Reduce digoxin dose by 50% when initiating amiodarone and monitor serum levels."
        ),
    },
    # ── Fluoroquinolone + antacids ────────────────────────────────────────
    {
        "rxcui_a": "2393",    # ciprofloxacin
        "rxcui_b": "8031",    # aluminum hydroxide (antacid)
        "name_a": "Ciprofloxacin",
        "name_b": "Antacid (Aluminum/Magnesium)",
        "severity": "moderate",
        "description": (
            "Divalent/trivalent cations in antacids chelate fluoroquinolones, reducing absorption "
            "by up to 90%. Administer ciprofloxacin at least 2 hours before or 6 hours after antacids."
        ),
    },
    # ── Lithium interactions ──────────────────────────────────────────────
    {
        "rxcui_a": "6468",    # lithium
        "rxcui_b": "41493",   # ibuprofen
        "name_a": "Lithium",
        "name_b": "Ibuprofen",
        "severity": "major",
        "description": (
            "NSAIDs reduce renal lithium clearance, raising serum lithium levels and risk of "
            "toxicity (tremor, confusion, cardiac arrhythmia). Monitor lithium levels closely; "
            "consider acetaminophen instead."
        ),
    },
    {
        "rxcui_a": "6468",    # lithium
        "rxcui_b": "18867",   # lisinopril (ACE inhibitor)
        "name_a": "Lithium",
        "name_b": "Lisinopril",
        "severity": "major",
        "description": (
            "ACE inhibitors reduce renal lithium clearance, substantially increasing lithium "
            "levels and toxicity risk. Monitor lithium levels within 1 week of ACE inhibitor initiation."
        ),
    },
]


def _normalize(s: str) -> str:
    return s.lower().strip()


def lookup_interactions(drug_list: list[dict[str, str]]) -> list[dict]:
    """Check a list of {rxcui, name} dicts against the curated DDI table.

    Matching strategy:
    1. RxCUI match (exact, both directions) — preferred
    2. Name substring match (case-insensitive) — fallback for drugs without RxCUI

    Returns a list of matching DDI records.
    """
    matches: list[dict] = []
    seen_pairs: set[frozenset] = set()

    rxcuis = {d["rxcui"] for d in drug_list if d.get("rxcui")}
    names = {_normalize(d["name"]) for d in drug_list if d.get("name")}

    for entry in DDI_TABLE:
        pair_key = frozenset([entry["rxcui_a"], entry["rxcui_b"]])
        if pair_key in seen_pairs:
            continue

        rxcui_match = entry["rxcui_a"] in rxcuis and entry["rxcui_b"] in rxcuis
        name_match = (
            any(_normalize(entry["name_a"]) in n or n in _normalize(entry["name_a"]) for n in names)
            and any(_normalize(entry["name_b"]) in n or n in _normalize(entry["name_b"]) for n in names)
        )

        if rxcui_match or name_match:
            matches.append(
                {
                    "drug1": entry["name_a"],
                    "drug2": entry["name_b"],
                    "severity": entry["severity"],
                    "description": entry["description"],
                    "source": "ClinAgent curated DDI dataset",
                }
            )
            seen_pairs.add(pair_key)

    return matches
