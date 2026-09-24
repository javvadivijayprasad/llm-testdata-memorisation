"""Five-element prompt-engineering taxonomy for RAITG.

The taxonomy:
  1. Role specification
  2. Context injection
  3. Task directive
  4. Heuristic scaffold
  5. Output contract
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROMPT_VERSION = "raitg-prompt-v1.5.1-oss-grounded-testdata"
# v1.5.0 (2026-09-12, Paper H / E2): optional [TEST DATA] element — a provisioned fixture block
# (SynthData functional / functional+edge+negative / the project's own fixture) appended to
# [CONTEXT]. Selected by test_data_arm in {"func","all","human","state"}; None reproduces v1.4.0 byte for
# byte. Blocks live in TESTDATA_DIR/<arm>/<target_app>.txt (MD5s in TESTDATA_MD5.txt); httpbin has
# no block in any arm (negative control).
TESTDATA_DIR = os.environ.get("RAITG_TESTDATA_DIR", str(Path(__file__).resolve().parent.parent / "testdata"))


def _load_test_data(target_app: str, arm: str | None) -> str:
    if not arm:
        return ""
    p = Path(TESTDATA_DIR) / arm / f"{target_app}.txt"
    return p.read_text(encoding="utf-8") if p.exists() else ""



# ---------------------------------------------------------------------------
# Element 1: role specification
# ---------------------------------------------------------------------------
ROLE_SENIOR_QA = (
    "You are a senior software quality engineer with 12+ years of experience "
    "designing test suites for production systems. You are fluent in BDD, "
    "Gherkin, pytest, Playwright, and REST API testing. You write tests that "
    "are precise, deterministic, and traceable to source requirements. You "
    "follow ISO/IEC/IEEE 29119-4 test design techniques."
)


# ---------------------------------------------------------------------------
# Element 2: context injection
# ---------------------------------------------------------------------------
# v1.4.0 (2026-09-10): OSS-benchmark source grounding.
# v1.3.0 resolved repo/<target_app>/app.py, which exists only for the retired
# self-authored SUTs; for the four OSS SUTs the file was absent, the loader
# returned "" and NO source was injected (run logs: 2,484-2,538 input tokens,
# identical to the no-source prompt). v1.4.0 injects the modules that carry
# the frozen mutants (BENCHMARK_MANIFEST.md); for httpbin/core.py only the 14
# scoped route handlers are injected (same scope as the mutant set).
SUT_SOURCE_BUDGET_CHARS = 40000
SUT_SOURCE_FILES = {
    "httpbin": [("httpbin/core.py", "scoped"), ("httpbin/helpers.py", "full")],
    "fastapi-restful": [("main.py", "full"), ("routes/player_route.py", "full"),
                        ("services/player_service.py", "full"),
                        ("models/player_model.py", "full"),
                        ("schemas/player_schema.py", "full")],
    "flaskr": [("flaskr/__init__.py", "full"), ("flaskr/db.py", "full"),
               ("flaskr/auth.py", "full"), ("flaskr/blog.py", "full")],
    "fastapi-task-manager": [("app/main.py", "full"), ("app/crud.py", "full"),
                             ("app/schemas.py", "full"), ("app/models.py", "full"),
                             ("app/database.py", "full")],
}
# httpbin scoped handlers: line ranges from BENCHMARK_MANIFEST.md (SUT 1)
HTTPBIN_SCOPED_RANGES = [(333, 345), (367, 379), (415, 429), (433, 447), (451, 465),
                         (469, 483), (538, 563), (573, 644), (732, 777), (825, 846),
                         (857, 879), (883, 910), (914, 941), (945, 969)]

# In-process import idiom per SUT (mirrors how each project's own tests import it;
# the scoring harness runs pytest with cwd = SUT root and the SUT root on sys.path).
SUT_IMPORT_HINT = {
    "httpbin": "from httpbin.core import app   # Flask; use app.test_client()",
    "fastapi-restful": "from main import app          # FastAPI; use fastapi.testclient.TestClient(app)",
    "flaskr": "from flaskr import create_app  # Flask factory; app = create_app({'TESTING': True, 'DATABASE': <tmp path>}); use app.test_client()",
    "fastapi-task-manager": "from app.main import app      # FastAPI; use fastapi.testclient.TestClient(app)",
}


def _scoped_functions(src: str, ranges: list[tuple[int, int]]) -> str:
    """Return the top-level functions (with decorators) intersecting any range."""
    import ast
    tree = ast.parse(src)
    lines = src.splitlines()
    out = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            s = min([d.lineno for d in n.decorator_list] + [n.lineno])
            e = n.end_lineno
            if any(not (e < a or s > b) for a, b in ranges):
                out.append(f"# --- lines {s}-{e} ---\n" + "\n".join(lines[s - 1:e]))
    return "\n\n".join(out)


def _load_sut_source(target_app: str) -> str:
    """Load the source of the modules under test for the OSS SUT (v1.4.0)."""
    import os
    if not target_app or target_app not in SUT_SOURCE_FILES:
        return ""
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    parts = []
    for rel, how in SUT_SOURCE_FILES[target_app]:
        fp = os.path.join(root, "repo", target_app, rel)
        try:
            with open(fp, "r", encoding="utf-8") as f:
                src = f.read()
        except FileNotFoundError:
            raise RuntimeError(f"SUT source missing: {fp} (grounding would be silently empty)")
        if how == "scoped":
            src = _scoped_functions(src, HTTPBIN_SCOPED_RANGES)
            parts.append(f"# ===== {rel} (scoped: the {len(HTTPBIN_SCOPED_RANGES)} route handlers under test) =====\n{src}")
        else:
            parts.append(f"# ===== {rel} =====\n{src}")
    text = "\n\n".join(parts)
    if len(text) > SUT_SOURCE_BUDGET_CHARS:
        text = text[:SUT_SOURCE_BUDGET_CHARS] + "\n\n# ... (truncated at source budget)"
    return text


def context_block(req: dict[str, Any], glossary: dict[str, str] | None = None,
                  exemplars: list[dict[str, Any]] | None = None, *,
                  inject_source: bool = True, requirement_text: bool = True,
                  test_data_arm: str | None = None) -> str:
    """v1.4.0: `inject_source=False` -> requirements-only arm (what v1.3.0 actually
    ran on the OSS benchmark); `requirement_text=False` -> source-first arm (the
    endpoint under test and the SUT source, but no natural-language requirement)."""
    parts = ["[CONTEXT]"]
    parts.append(f"Requirement ID: {req['id']}")
    parts.append(f"Domain: {req['domain']}")
    parts.append(f"Layer: {req['layer']}")
    if requirement_text:
        parts.append(f"Category: {req['category']}")
        parts.append(f"Title: {req['title']}")
        parts.append(f"Statement: {req['statement']}")
        parts.append(f"Actors: {', '.join(req.get('actors') or [])}")
        parts.append(f"Preconditions: {'; '.join(req.get('preconditions') or [])}")
        parts.append(f"Triggers: {'; '.join(req.get('triggers') or [])}")
        parts.append(f"Expected outcomes: {'; '.join(req.get('expected_outcomes') or [])}")
        parts.append(f"Error pathways: {'; '.join(req.get('error_pathways') or [])}")
    parts.append(f"Target app: {req.get('target_app')}")
    parts.append(f"Endpoint/screen: {req.get('target_endpoint_or_screen')}")
    hint = SUT_IMPORT_HINT.get(req.get("target_app", ""))
    if hint:
        parts.append(f"In-process import for this app: {hint}")

    sut_src = _load_sut_source(req.get("target_app", "")) if inject_source else ""
    if sut_src:
        parts.append("")
        parts.append("[TARGET SUT SOURCE — use ONLY names that exist in this source]")
        parts.append("The modules under test for {} are below (project source, unmodified).".format(
            req.get("target_app")))
        parts.append("CRITICAL: Only reference methods, class names, and dataclass fields")
        parts.append("that EXIST in this source. Do NOT invent attributes like")
        parts.append("`notification_sent`, `status`, `error_code`, or any other field")
        parts.append("that is not visible in the source below. Hallucinated attributes")
        parts.append("will cause AttributeError and your test will contribute ZERO to")
        parts.append("mutation kill rate.")
        parts.append("```python")
        parts.append(sut_src)
        parts.append("```")

    td = _load_test_data(req.get("target_app", ""), test_data_arm)
    if td:
        parts.append("")
        parts.append(td.rstrip())
        parts.append("Use these rows and credentials in your tests instead of inventing data; the")
        parts.append("database under test is (re)loaded with the PRE-LOADED rows before every test.")

    if glossary:
        parts.append(f"Glossary: {json.dumps(glossary)}")
    if exemplars:
        parts.append("Exemplars (for style only, do not copy):")
        for ex in exemplars[:3]:
            parts.append("---")
            parts.append(json.dumps(ex, indent=2))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Element 3: task directive
# ---------------------------------------------------------------------------
FRAMEWORK_HINTS = {
    "pytest": (
        "Emit Python test functions named test_* that can run under `pytest`. "
        "Prefer `requests` or simple `httpx` for API assertions; avoid heavy fixtures."
    ),
    "playwright-ts": (
        "Emit TypeScript tests using `@playwright/test`. Use `test()`, `expect()`, "
        "page.getByRole / getByTestId. Avoid arbitrary sleeps; use expect() with auto-wait."
    ),
    "selenium-java": (
        "Emit a Java JUnit5 test class using Selenium WebDriver 4+. Use @Test, "
        "Assertions, WebDriverWait with ExpectedConditions. No Thread.sleep."
    ),
    "selenium-python": (
        "Emit pytest tests using selenium.webdriver. Use WebDriverWait + expected_conditions. "
        "Prefer explicit waits over sleep."
    ),
    "selenium-ts": (
        "Emit TypeScript/Mocha tests using selenium-webdriver. Use until.elementLocated."
    ),
    "cypress-ts": (
        "Emit Cypress TypeScript specs using `describe/it`, `cy.visit()`, `cy.get()`, "
        "`cy.contains()`, and `cy.request()`. Use `.should()` for assertions."
    ),
    "gherkin": (
        "Emit a Gherkin .feature file with Given/When/Then steps. One Feature, multiple Scenarios.\n"
        "  CRITICAL: Use ONLY these step patterns, which are the only ones the runtime\n"
        "  implements. Tests using other patterns will report 'undefined' and be skipped.\n\n"
        "  Login / navigation:\n"
        "    Given I am on the login page\n"
        "    When  I sign in with valid credentials\n"
        "    Then  I should see the dashboard\n"
        "    Then  Logout button is visible on the resulting page\n\n"
        "  Form interaction (always quote selectors and values):\n"
        "    When  Locate the <field-name> field with selector '<css-selector>'\n"
        "    When  Enter the value '<value>' into the <field-name> field\n"
        "    When  Leave the <field-name> field '<css-selector>' completely empty\n"
        "    When  Click the <text> button\n"
        "    When  Click the button with selector '<css-selector>'\n"
        "    When  Wait for navigation or page content to update\n"
        "    When  Wait for the error message element to appear\n\n"
        "  Assertions:\n"
        "    Then  User is redirected to <description> (URL contains '<fragment>')\n"
        "    Then  User is NOT redirected away from the login page\n"
        "    Then  URL remains on the login page\n"
        "    Then  Page body contains text '<expected text>'\n"
        "    Then  Error message text contains '<expected text>'\n"
        "    Then  An error message element with id '<id>' becomes visible\n"
        "    Then  An error message or validation indicator becomes visible\n\n"
        "  Map every requirement onto these patterns. For non-login domains, frame the\n"
        "  scenario as a login-style flow (e.g. 'I sign in', 'I should see the dashboard')\n"
        "  rather than inventing new step text. NEVER use abstract phrasing like\n"
        "  'invoke requirement X in positive mode' — use concrete UI steps from this list."
    ),
    # cucumber-js shares Gherkin .feature syntax. The cloud-job runtime executes
    # @cucumber/cucumber against a step-definitions library, so we MUST limit the
    # generated steps to the patterns the library implements. The actions/expected
    # values become the When/Then step text, so they need to be valid step lookups,
    # not abstract prose like "invoke requirement X in positive mode".
    "cucumber-js": (
        "Emit Gherkin step text that runs against @cucumber/cucumber + Playwright.\n"
        "  STRUCTURE: classic BDD with proper Given/When/Then + And connectors.\n"
        "  Each scenario should follow this template:\n\n"
        "    Background:                              ← shared across scenarios\n"
        "      Given I am on the login page          ← single navigation step\n\n"
        "    Scenario: <descriptive name>\n"
        "       When <first action>                  ← one When\n"
        "        And <second action>                  ← rest are And\n"
        "        And <third action>\n"
        "        And <wait step if needed>\n"
        "       Then <first assertion>               ← one Then\n"
        "        And <second assertion>               ← rest are And\n"
        "        And <third assertion>\n\n"
        "  RULES:\n"
        "    1. Put 'I am on the login page' in Background, NOT inside each Scenario.\n"
        "    2. Use 'And' to chain multi-step phases. NEVER write two When in a row\n"
        "       or two Then in a row — use When + And + And ... and Then + And + And.\n"
        "    3. Aim for 3-5 steps per phase. Granular = better debug signal.\n"
        "    4. Tag each scenario with @<kind> @<heuristic> e.g. @positive @ep,\n"
        "       @negative @neg, @boundary @bva.\n\n"
        "  CRITICAL: The 'actions' and 'expected' fields become When/Then step text.\n"
        "  They MUST match one of the step-definition patterns below — no other text\n"
        "  is recognised, and unrecognised steps are reported 'undefined' and skipped.\n\n"
        "  Login / navigation steps (use these for any auth-related case):\n"
        "    actions:  ['I am on the login page', 'I sign in with valid credentials']\n"
        "    expected: ['I should see the dashboard']\n\n"
        "  Form interaction (selectors and values must be quoted):\n"
        "    actions:  [\"Locate the username field with selector '#username'\",\n"
        "              \"Enter the value 'demo' into the username field\",\n"
        "              \"Click the 'Sign In' button\",\n"
        "              'Wait for navigation or page content to update']\n\n"
        "  Negative-path actions (empty fields, bad credentials):\n"
        "    actions:  [\"Leave the password field '#password' completely empty\",\n"
        "              \"Click the 'Sign In' button\",\n"
        "              'Wait for the error message element to appear']\n\n"
        "  Allowed expected/Then patterns:\n"
        "    'I should see the dashboard'\n"
        "    'Logout button is visible on the resulting page'\n"
        "    \"User is redirected to dashboard (URL contains '/dashboard')\"\n"
        "    'User is NOT redirected away from the login page'\n"
        "    'URL remains on the login page'\n"
        "    \"Page body contains text 'Welcome'\"\n"
        "    \"Error message text contains 'Invalid credentials'\"\n"
        "    \"An error message element with id 'error-banner' becomes visible\"\n"
        "    'An error message or validation indicator becomes visible'\n\n"
        "  Frame EVERY requirement (any domain — banking, HR, FHIR, etc.) as a\n"
        "  login-style web-form flow against these patterns. Treat the requirement's\n"
        "  business intent as the 'why', and pick the closest concrete UI flow as the\n"
        "  'how'. NEVER emit abstract prose like 'invoke requirement X in positive\n"
        "  mode' or 'successful response' — those will be reported as undefined.\n\n"
        "  REAL BDD STRUCTURE — multi-step Given/When/Then with And:\n"
        "  Real-world Gherkin reads like a story. Each phase has multiple atomic\n"
        "  steps connected by And, not one long sentence. The emitter turns the\n"
        "  first item in each array into Given/When/Then and the rest into And.\n"
        "  Aim for 2-4 entries per array — granular enough to debug, narrative\n"
        "  enough to read.\n\n"
        "  EXAMPLE of the structure expected (positive login case):\n"
        "    preconditions: [\n"
        "      \"I am on the login page\",\n"
        "      \"the username field is empty\",\n"
        "      \"the password field is empty\"\n"
        "    ]\n"
        "    actions: [\n"
        "      \"Enter the value 'student' into the username field\",\n"
        "      \"Enter the value 'Password123' into the password field\",\n"
        "      \"Click the 'Sign In' button\",\n"
        "      \"Wait for navigation or page content to update\"\n"
        "    ]\n"
        "    expected: [\n"
        "      \"User is redirected to dashboard (URL contains '/dashboard')\",\n"
        "      \"Page body contains text 'Welcome'\",\n"
        "      \"Logout button is visible on the resulting page\"\n"
        "    ]\n\n"
        "  The emitter renders this as:\n"
        "    Given I am on the login page\n"
        "      And the username field is empty\n"
        "      And the password field is empty\n"
        "     When Enter the value 'student' into the username field\n"
        "      And Enter the value 'Password123' into the password field\n"
        "      And Click the 'Sign In' button\n"
        "      And Wait for navigation or page content to update\n"
        "     Then User is redirected to dashboard (URL contains '/dashboard')\n"
        "      And Page body contains text 'Welcome'\n"
        "      And Logout button is visible on the resulting page\n\n"
        "  MANDATORY FIRST PRECONDITION: every scenario MUST start preconditions\n"
        "  with \"I am on the login page\" (or equivalent navigation step). Without\n"
        "  this, the runner never calls page.goto() and all clicks/fills time out\n"
        "  on about:blank. Add additional preconditions after that as needed.\n\n"
        "  Avoid one-step phases. A scenario with a single action and a single\n"
        "  expected outcome is technically valid but not realistic — break login\n"
        "  into ENTER USERNAME, ENTER PASSWORD, CLICK SUBMIT as separate actions.\n\n"
        "  ALLOWED PHRASINGS — you MUST emit step text using ONLY the templates\n"
        "  in this list. The downstream parser (bdd2pw) only matches these exact\n"
        "  shapes; anything else falls through to TODO (no executable code) and\n"
        "  the test silently passes without doing what it claims. DO NOT invent\n"
        "  new phrasings. DO NOT append parenthetical commentary like\n"
        "  '(URL changes away from login page)' — the parenthetical becomes part\n"
        "  of the regex slug and breaks the match.\n\n"
        "  Navigation:\n"
        "    \"I am on the login page\"\n"
        "    \"I sign in with valid credentials\"\n"
        "    \"I should see the dashboard\"\n\n"
        "  Form interaction (selectors and values must be quoted):\n"
        "    \"Locate the <field> field with selector '<css>'\"\n"
        "    \"Enter the value '<value>' into the <field> field\"\n"
        "    \"Leave the <field> field '<css>' completely empty\"\n"
        "    \"Click the '<text>' button\"\n"
        "    \"Click the button with selector '<css>'\"\n"
        "    \"Wait for navigation or page content to update\"\n"
        "    \"Wait for the error message element to appear\"\n\n"
        "  Assertions:\n"
        "    \"User is redirected to <description> (URL contains '<fragment>')\"\n"
        "    \"User is NOT redirected away from the login page\"\n"
        "    \"URL remains on the login page\"\n"
        "    \"Page body contains text '<expected text>'\"\n"
        "    \"Error message text contains '<expected text>'\"\n"
        "    \"An error message element with id '<id>' becomes visible\"\n"
        "    \"An error message or validation indicator becomes visible\"\n"
        "    \"Logout button is visible on the resulting page\"\n\n"
        "  FORBIDDEN — these will silently break the test (parser falls through\n"
        "  to TODO and the test passes without doing anything):\n"
        "    ✗ \"Enter 'X' in the username field\"        (use 'into', not 'in')\n"
        "    ✗ \"User is redirected to logged-in page\"   (no URL fragment given;\n"
        "                                                  needs '(URL contains ...)')\n"
        "    ✗ \"User remains on login page (URL ...)\"  (parenthetical breaks slug;\n"
        "                                                  use 'URL remains on the\n"
        "                                                  login page' instead)\n"
        "    ✗ Anything starting with abstract words like 'invoke', 'verify the\n"
        "      requirement', 'successful response', 'documented error'\n\n"
        "  DATA-DRIVEN MODE: If the [CONTEXT] block contains 'TEST DATA AVAILABLE',\n"
        "  the user has uploaded a sample data file (CSV/JSON) and listed its columns\n"
        "  + a few example rows. In that case:\n"
        "    1. Emit at least one test where `kind` is 'positive' or 'boundary' as a\n"
        "       data-driven case. The `name` should describe the parametric intent.\n"
        "    2. Populate the test's `data` field (top-level on each test object) with\n"
        "       a column-major dict using the columns listed in the context. Each\n"
        "       column maps to an array of length N (one entry per row). Pull values\n"
        "       directly from the sample rows the context shows.\n"
        "       Example: data = { \"username\": [\"alice\", \"bob\"],\n"
        "                          \"password\": [\"Pass1!\", \"Pass2!\"],\n"
        "                          \"expected\": [\"dashboard\", \"locked\"] }\n"
        "    3. Reference the column names with angle brackets in the action/expected\n"
        "       step text (Gherkin Examples-table syntax):\n"
        "         actions:  [\"Enter the value '<username>' into the username field\",\n"
        "                    \"Enter the value '<password>' into the password field\",\n"
        "                    \"Click the 'Sign In' button\"]\n"
        "         expected: [\"Page body contains text '<expected>'\"]\n"
        "    4. The downstream emitter will turn `data` into Gherkin Scenario Outline\n"
        "       + Examples table — one parametric test per row, run against real\n"
        "       user-supplied values. Do NOT invent placeholders ('username',\n"
        "       'password123') when real data is available."
    ),
    "postman": (
        "Emit a Postman v2.1 collection JSON with Pre-request and Test scripts "
        "using pm.test() and pm.expect()."
    ),
}


def task_directive(target_framework: str) -> str:
    hint = FRAMEWORK_HINTS.get(target_framework, "")
    hint_block = f"\n\nFRAMEWORK NOTES:\n  {hint}" if hint else ""
    return (
        "[TASK]\n"
        "Generate a test suite for the requirement above. The suite must include "
        "AT LEAST one positive case, one negative case, and one boundary case. "
        f"The target framework is {target_framework}. "
        "Each test case must be self-contained, deterministic, and idempotent.\n\n"
        "IMPORTANT LIMITS:\n"
        "  - Keep each `executable` field to AT MOST 40 lines of code.\n"
        "  - The `executable` field MUST be SELF-CONTAINED, runnable Python code.\n"
        "    NO placeholders like <helper_fn>, <fixture>, <mock>, <TODO>.\n"
        "    NO undefined function or class references.\n"
        "  - The target_app (see [CONTEXT]) is a real open-source Python web service.\n"
        "    Import it IN-PROCESS using the import shown in [CONTEXT] and drive it\n"
        "    with the framework test client (Flask app.test_client() or\n"
        "    fastapi.testclient.TestClient). NEVER call a live URL (no http://localhost,\n"
        "    no httpbin.org): the tests are executed against a mutated in-process copy\n"
        "    of the source, so a live-URL test can detect nothing.\n"
        "  - The test body must be executable at MODULE-LEVEL (not inside `def test_*`),\n"
        "    like the baseline test suite in scripts/baseline_tests.py.\n"
        "    Use plain `assert` statements + try/except to trap expected errors.\n"
        "  - Do NOT include license headers, long import lists, or multi-line docstrings.\n"
        "  - Always properly escape internal double-quotes in JSON string values.\n"
        "  - Prefer concise assertions over comprehensive setup/teardown.\n"
        "  - Every test's `executable` code will be EXECUTED against mutants of the\n"
        "    target app. If the code crashes with SyntaxError or NameError, the test\n"
        "    contributes ZERO to mutation kill rate. Write code that actually runs."
        + hint_block
    )


# ---------------------------------------------------------------------------
# Element 4: heuristic scaffold
# ---------------------------------------------------------------------------
HEURISTIC_SCAFFOLD = (
    "[HEURISTICS]\n"
    "Apply the following classical test design heuristics; cite which heuristic each "
    "test embodies in the `heuristic` field:\n"
    "  - Equivalence Partitioning (EP)\n"
    "  - Boundary Value Analysis (BVA)\n"
    "  - State Transition Coverage (STC)\n"
    "  - Decision Table (DT)\n"
    "  - Negative Path (NEG)"
)


# ---------------------------------------------------------------------------
# Element 6: mutation resilience (added 2026-08-04 in response to Menzies R1 review)
# ---------------------------------------------------------------------------
MUTATION_RESILIENCE = (
    "[MUTATION RESILIENCE]\n"
    "Your tests will be scored by executable mutation testing (mutmut). A "
    "MUTATION-RESILIENT test suite kills common mutation operators. Follow "
    "these rules for every test you write:\n\n"
    "  1. ASSERT EXACT VALUES, not existence.\n"
    "     BAD:  assert result is not None\n"
    "     BAD:  assert response.status_code >= 200\n"
    "     GOOD: assert result == 42\n"
    "     GOOD: assert response.status_code == 200\n"
    "     GOOD: assert response.json() == {\"balance\": 500, \"currency\": \"USD\"}\n\n"
    "  2. TEST BOTH SIDES of every comparison operator in the code under test.\n"
    "     For x >= threshold, write:\n"
    "       - a test where x == threshold-1 (should fail the condition)\n"
    "       - a test where x == threshold (should pass — this catches > vs >=)\n"
    "       - a test where x == threshold+1 (should pass)\n"
    "     This catches mutations that flip <, <=, >, >=, ==, !=.\n\n"
    "  3. TEST BOUNDARY ±1 for every numeric threshold, quantity, or index.\n"
    "     If code uses limit=100, test at 99, 100, 101 (not just at 50).\n"
    "     This catches off-by-one mutations (n -> n+1, n -> n-1).\n\n"
    "  4. ASSERT ARITHMETIC OUTPUTS EXACTLY.\n"
    "     For code that returns x + y, do not just check that a number is returned.\n"
    "     Compute the expected value in the test and assert equality:\n"
    "       assert calculate(3, 5) == 8    # catches + -> -, + -> *, etc.\n\n"
    "  5. ASSERT ON BOOLEAN INVARIANTS both true AND false.\n"
    "     If code has `if verified and tier == 'premium':`, write:\n"
    "       - test with verified=True, tier='premium' (both branches true)\n"
    "       - test with verified=False, tier='premium' (short-circuits on verified)\n"
    "       - test with verified=True, tier='standard' (short-circuits on tier)\n"
    "     This catches `and -> or` and boolean negation mutations.\n\n"
    "  6. COVER NEGATIVE-PATH RETURN VALUES, not just exceptions.\n"
    "     If a function returns None on invalid input, assert:\n"
    "       assert function(bad_input) is None    # not just: with pytest.raises(...)\n"
    "     This catches mutations that suppress the None-return path.\n\n"
    "  7. FOR EVERY CONSTANT in the code (limits, thresholds, error codes, magic\n"
    "     numbers), write a test whose ASSERTION uses that exact constant. If the\n"
    "     constant is mutated (100 -> 101, \"ERR_001\" -> \"XX_001\"), your test\n"
    "     must fail.\n\n"
    "  8. AVOID GENERIC ASSERTIONS like `assert True`, `assert response`, or\n"
    "     `assert isinstance(x, dict)` without also asserting the dict's contents.\n"
    "     Every assertion should distinguish the correct implementation from a\n"
    "     subtly wrong implementation.\n\n"
    "The scoring rubric: a test that passes on the correct code but ALSO passes on\n"
    "code with a small semantic change (operator flip, constant bump, boolean\n"
    "negation) is a weak test. Aim for tests that FAIL when the code is subtly\n"
    "wrong. Rate your own tests before returning: for each test, briefly note in\n"
    "the `heuristic` field which mutation operator(s) it is designed to catch\n"
    "(e.g. \"BVA + boundary-mutation\", \"EP + comparison-mutation\").\n\n"
    "REFERENCE EXAMPLE — a mutation-resilient in-process web-service test:\n"
    "```python\n"
    "from flaskr import create_app                     # in-process import (see [CONTEXT])\n"
    "import tempfile, os\n"
    "fd, path = tempfile.mkstemp(); os.close(fd)\n"
    "app = create_app({'TESTING': True, 'DATABASE': path})\n"
    "client = app.test_client()\n"
    "r = client.post('/auth/register', data={'username': 'a', 'password': 'a'})\n"
    "assert r.status_code == 302                       # exact status, not >= 200\n"
    "assert r.headers['Location'] == '/auth/login'     # exact redirect target\n"
    "r = client.post('/auth/register', data={'username': '', 'password': 'a'})\n"
    "assert b'Username is required.' in r.data         # exact error text (negative path)\n"
    "r = client.post('/auth/register', data={'username': 'a', 'password': 'a'})\n"
    "assert b'already registered' in r.data            # duplicate boundary\n"
    "```\n"
    "Notice: no placeholders, direct imports, exact-value assertions,\n"
    "boundary ±1, both operand paths of any `or` short-circuit tested."
)


# ---------------------------------------------------------------------------
# Element 5: output contract
# ---------------------------------------------------------------------------
OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["requirement_id", "reasoning", "tests"],
    "properties": {
        "requirement_id": {"type": "string"},
        "reasoning": {"type": "string"},
        "tests": {
            "type": "array",
            "minItems": 3,
            "items": {
                "type": "object",
                "required": ["name", "kind", "heuristic", "preconditions",
                             "actions", "expected", "trace", "executable"],
                "properties": {
                    "name": {"type": "string"},
                    "kind": {"type": "string", "enum": ["positive", "negative", "boundary"]},
                    "heuristic": {"type": "string", "enum": ["EP", "BVA", "STC", "DT", "NEG"]},
                    "preconditions": {"type": "array", "items": {"type": "string"}},
                    "actions": {"type": "array", "items": {"type": "string"}},
                    "expected": {"type": "array", "items": {"type": "string"}},
                    "trace": {"type": "array", "items": {"type": "string"}},
                    "executable": {"type": "string",
                                    "description": "Self-contained runnable Python code, module-level (no def test_* wrapper). Must import directly from `app` (the target SUT module) and use plain assert/try-except. NO placeholders."},
                }
            }
        }
    }
}


def output_contract(target_framework: str) -> str:
    return (
        "[OUTPUT]\n"
        "Respond with VALID JSON ONLY conforming to the schema below. "
        "No prose outside the JSON. The `executable` field must contain "
        f"runnable {target_framework} source code for the test, ready to "
        "execute against the target system without modification.\n"
        f"Schema:\n{json.dumps(OUTPUT_SCHEMA, indent=2)}"
    )


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------
def compose_prompt(req: dict[str, Any], target_framework: str = "pytest",
                   glossary: dict[str, str] | None = None,
                   exemplars: list[dict[str, Any]] | None = None,
                   *, mode: str = "full", inject_source: bool = True,
                   requirement_text: bool = True, test_data_arm: str | None = None) -> str:
    """Compose the full RAITG prompt.

    mode:
      "full"        — all five elements (RAITG)
      "no-heuristic" — ablation (drop element 4)
      "no-contract" — ablation (drop element 5)
      "naive"       — unverified-LLM baseline (just role + requirement)
    """
    if mode == "naive":
        return (
            f"You are a quality engineer. Write {target_framework} tests "
            f"for the requirement: {req['statement']}"
        )

    parts = [f"[ROLE]\n{ROLE_SENIOR_QA}",
             context_block(req, glossary, exemplars, inject_source=inject_source,
                           requirement_text=requirement_text, test_data_arm=test_data_arm),
             task_directive(target_framework)]
    if mode != "no-heuristic":
        parts.append(HEURISTIC_SCAFFOLD)
    # v1.1.0: mutation-resilience element (added in R2 revision after Menzies' review)
    # Enabled for "full" mode; ablation modes can be added later ("no-mutation").
    if mode == "full":
        parts.append(MUTATION_RESILIENCE)
    if mode != "no-contract":
        parts.append(output_contract(target_framework))
    return "\n\n".join(parts)


def repair_prompt(req: dict[str, Any], original: str,
                  rule_violations: list[str]) -> str:
    """Build a targeted repair prompt for verification failures.

    Supplies the original requirement, the failed response, and the
    specific violations so that the LLM can patch rather than
    regenerate from scratch.
    """
    return (
        "[ROLE]\n"
        + ROLE_SENIOR_QA +
        "\n\n[TASK]\nYour previous response failed rule-based verification. "
        "FIX every violation listed below while PRESERVING all tests that already pass. "
        "Do NOT discard the original structure. Do NOT emit an empty object. "
        "Do NOT wrap the JSON in markdown code fences or prose.\n\n"
        "[VIOLATIONS]\n- " + "\n- ".join(rule_violations) +
        "\n\n[ORIGINAL REQUIREMENT]\n" + json.dumps(req, indent=2) +
        "\n\n[YOUR PREVIOUS RESPONSE]\n" + original[:8000] +
        "\n\n[OUTPUT]\nRespond with VALID JSON ONLY conforming to the following schema. "
        "No prose, no code fences.\nSchema:\n"
        + json.dumps(OUTPUT_SCHEMA, indent=2)
    )
