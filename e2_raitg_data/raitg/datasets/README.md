# Requirement datasets

Three requirement corpora spanning distinct industry domains, structured after the style of acceptance criteria found in permissively licensed open-source projects (Gitea, Ghost, Gogs, Supabase, LinuxForHealth FHIR). Requirements are authored for the purposes of this study and are not direct reproductions; style and functional surface are mirrored but phrasing, identifiers, and business rules are independent.

## Files

- `commercial_web.json` — 112 requirements for a human-resources management web application (`repo/hr-app`).
- `financial_services.json` — 98 requirements for a retail account-management API (`repo/banking-api`).
- `healthcare.json` — 102 requirements for a FHIR-lite information exchange (`repo/fhir-lite`).
- `combined.json` — concatenation with source-dataset tags.

## Schema

```json
{
  "id": "R-WEB-001",
  "domain": "commercial_web",
  "layer": "UI | API | INTEGRATION",
  "category": "auth | validation | transaction | reporting | integration",
  "title": "short human-readable title",
  "statement": "natural-language requirement text",
  "actors": ["authenticated user", "admin"],
  "preconditions": ["user is authenticated"],
  "triggers": ["user submits form"],
  "expected_outcomes": ["record created", "audit log written"],
  "error_pathways": ["validation error", "permission denied"],
  "target_app": "hr-app",
  "target_endpoint_or_screen": "/employees/create"
}
```

## Provenance

Requirements are generated deterministically by `scripts/generate_requirements.py` from seed tables stored in `datasets/seeds/`. Re-running the generator with the same seed reproduces the dataset exactly.
