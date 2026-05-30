"""
Example: call the Synthea API Apify Actor from Python.

Synthea generates synthetic, FHIR-compliant patient health records. The data is
entirely fabricated, so it is safe for testing, demos, ML training, and FHIR
pipeline development without any real protected health information (PHI).

Each run returns a dataset item that summarizes the generation and lists the
output files; the full FHIR bundles are stored in the run's key-value store and
referenced by key. This example generates one patient, prints the summary, then
fetches the patient's FHIR bundle from the key-value store and reports its
resource types and demographics. Inputs are kept small (one patient) so the
first run is inexpensive; each patient generated is billed.

Get your free Apify API key at: https://apify.com?fpr=9n7kx3
Set it in a .env file (see .env.example) or export APIFY_API_TOKEN.
"""

import collections
import json
import os

from apify_client import ApifyClient
from dotenv import load_dotenv

load_dotenv()

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
if not APIFY_API_TOKEN:
    raise SystemExit(
        "APIFY_API_TOKEN is not set. Copy .env.example to .env and add your key, "
        "or run: export APIFY_API_TOKEN=your_api_key_here"
    )

client = ApifyClient(APIFY_API_TOKEN)

run_input = {
    "population_size": 1,
    "seed": 1,                 # fixed seed = reproducible patients
    "age_range": "30-40",
    "state": "Massachusetts",
}

print(f"Generating {run_input['population_size']} synthetic patient(s)...")
run = client.actor("johnvc/Synthea-Medical-Record-Generator-API").call(run_input=run_input)
if run is None:
    raise SystemExit("The Actor run did not start. Check your API token and inputs.")

items = list(client.dataset(run.default_dataset_id).iterate_items())
record = items[0]
summary = record.get("summary", {})
print(f"\nPatients generated: {summary.get('patient_count')}")
print(f"FHIR files: {summary.get('total_fhir_files')}, metadata files: {summary.get('total_metadata_files')}\n")

files = record.get("data", {}).get("fhir_bundles", [])
print("Generated FHIR files:")
for f in files:
    print(f"  - {f.get('file')}  ({f.get('size_mb')} MB)")

# The bundle contents live in the run's key-value store; fetch one by its key.
kv_store = client.key_value_store(run.default_key_value_store_id)
patient_file = next(
    (f for f in files if not f.get("file", "").lower().startswith(("hospital", "practitioner"))),
    files[0] if files else None,
)
if patient_file:
    rec = kv_store.get_record(patient_file["key_value_store_key"])
    bundle = rec["value"] if rec else None
    if isinstance(bundle, str):
        bundle = json.loads(bundle)

    entries = bundle.get("entry", []) if bundle else []
    types = collections.Counter(
        e.get("resource", {}).get("resourceType") for e in entries
    )
    print(f"\nPatient bundle: {len(entries)} FHIR resources")
    for rtype, count in types.most_common(8):
        print(f"  {rtype}: {count}")

    patient = next(
        (e["resource"] for e in entries if e.get("resource", {}).get("resourceType") == "Patient"),
        None,
    )
    if patient:
        address = (patient.get("address") or [{}])[0]
        print(
            f"\nPatient: {patient.get('gender')}, born {patient.get('birthDate')}, "
            f"{address.get('city')}, {address.get('state')} (synthetic)"
        )
