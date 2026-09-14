"""
scripts/new_vertical.py

Scaffolds a new domain vertical from agents/_template/.

The README documents eight manual steps for adding a vertical. Steps 1-6
are mechanical copying and renaming; steps 7 and 8 — the eval case file and
the boundary test's suspicious_tokens entry — are the ones that get skipped,
and skipping them is quiet. A vertical missing its eval file has no routing
accuracy gate, and a vertical missing its token is not actually checked for
leaking into core/. Both look fine until they matter.

This script does all eight, so the failure mode isn't available.

    python -m scripts.new_vertical clinic_ops
    python -m scripts.new_vertical clinic_ops --activate
    python -m scripts.new_vertical clinic_ops --dry-run

What it writes:
    agents/{domain}/                     copied from _template, identifiers renamed
    tests/eval/test_{domain}_decisions.py    routing eval gate, green on arrival
    tests/test_architecture_boundary.py      appends "{domain}" to suspicious_tokens
    api/main.py                          only with --activate

core/ and governance/ are never touched — by this script, or by the vertical
it produces. That is the property the boundary test enforces.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = REPO_ROOT / "agents" / "_template"
BOUNDARY_TEST = REPO_ROOT / "tests" / "test_architecture_boundary.py"
API_MAIN = REPO_ROOT / "api" / "main.py"

VALID_NAME = re.compile(r"[a-z][a-z0-9_]*\Z")


class ScaffoldError(RuntimeError):
    """Anything that should stop the scaffold with a readable message."""


# --------------------------------------------------------------------------
# naming
# --------------------------------------------------------------------------


def class_prefix(domain: str) -> str:
    """clinic_ops -> ClinicOps"""
    return "".join(part.capitalize() for part in domain.split("_"))


def validate_domain(domain: str) -> None:
    if not VALID_NAME.match(domain):
        raise ScaffoldError(
            f"'{domain}' is not a usable package name.\n"
            "Use lowercase letters, digits and underscores, starting with a letter "
            "(e.g. clinic_ops, logistics, tenant_support)."
        )
    if domain.startswith("_"):
        raise ScaffoldError(f"'{domain}' starts with an underscore, which is reserved.")
    if domain in {"template", "core", "governance", "api", "console", "tests", "scripts"}:
        raise ScaffoldError(f"'{domain}' collides with an existing top-level package name.")


# --------------------------------------------------------------------------
# file rewriting
# --------------------------------------------------------------------------


def rename_identifiers(text: str, domain: str) -> str:
    """Swap every template identifier for its domain equivalent.

    Applied longest-key-first so that no replacement can corrupt a longer
    identifier it happens to be a prefix of.
    """
    cls = class_prefix(domain)
    replacements = {
        "TemplateDomainContext": f"{cls}DomainContext",
        "TemplateExampleTool": f"{cls}ExampleTool",
        "template_example_tool": f"{domain}_example_tool",
        "TemplateAgent": f"{cls}Agent",
        "template_agent": f"{domain}_agent",
        "agents/_template": f"agents/{domain}",
        "agents._template": f"agents.{domain}",
    }
    for old, new in COMMENT_REWRITES.items():
        text = text.replace(old, new)
    for old in sorted(replacements, key=len, reverse=True):
        text = text.replace(old, replacements[old])
    return text


def swap_module_docstring(text: str, new_docstring: str) -> str:
    """Replace a module's leading docstring, leaving the code untouched.

    The template's docstrings are addressed to someone about to copy the
    template by hand; in a generated file they describe a step that already
    happened. Returns the text unchanged if there is no leading docstring.
    """
    stripped = text.lstrip()
    if not stripped.startswith('"""'):
        return text
    leading = len(text) - len(stripped)
    end = stripped.find('"""', 3)
    if end == -1:
        return text
    return text[:leading] + f'"""\n{new_docstring.strip()}\n"""' + stripped[end + 3 :]


# Inline comments in the template that address someone copying it by hand.
# In a generated file they describe a step that already happened, and this one
# sits in can_handle() — the method a new adopter reads first.
COMMENT_REWRITES = {
    """        # Replace with real heuristic / classifier call. Returning a flat
        # 0.0 here means this template agent never actually claims a
        # request — intentional, so copying the template without editing
        # can_handle() can't silently start routing real traffic to it.""": """        # Replace with a real heuristic or classifier call. Returning a flat
        # 0.0 means this agent never claims a request — deliberate, so a
        # scaffolded vertical can't start routing real traffic before anyone
        # has said what it handles.""",
}


DOCSTRINGS = {
    "agent.py": """
agents/{domain}/agent.py

Specialist agents for the {domain} vertical.

Each agent implements core.contracts.SpecialistAgent structurally — no base
class, just matching shape. The supervisor scores can_handle() across every
registered agent and routes to the highest.

TO FINISH THIS VERTICAL:
  1. Rename {cls}Agent to something real, and add more agent classes
     as needed — most verticals want 3-5.
  2. Write can_handle(): return a confidence in [0.0, 1.0]. A keyword
     heuristic is a fine start. It currently returns 0.0, which means this
     agent never claims anything — deliberate, so a half-finished vertical
     can't silently take production traffic.
  3. Write execute(): the actual work. Do not add audit or guardrail calls;
     governance wraps this automatically.
  4. Set always_gate = True on any agent whose actions need human approval
     before they run. graph_builder reads it at BUILD time and wires an
     HITL gate node in front of that agent.
  5. Register every agent you add at the bottom of this file.
  6. Fill in tests/eval/test_{domain}_decisions.py with real routing cases.
""",
    "schemas.py": """
agents/{domain}/schemas.py

This vertical's typed view into AgentState.domain_context.

core/ passes domain_context through as an untyped dict and never inspects
it — this model is where {domain} validates at its own boundary. Replace
the example fields with what this domain actually carries.
""",
    "tools.py": """
agents/{domain}/tools.py

Tools for the {domain} vertical.

Tools implement core.contracts.BaseTool structurally and register themselves
on import, so an agent can name them in required_tools() and the eval harness
can check they exist. Replace the example tool with real ones.
""",
    "prompts.py": """
agents/{domain}/prompts.py

Prompts for the {domain} vertical, as plain module-level constants — easy to
diff in review, easy to eval against.
""",
}


# --------------------------------------------------------------------------
# generated eval stub
# --------------------------------------------------------------------------

EVAL_TEMPLATE = '''"""
tests/eval/test_{domain}_decisions.py

Routing-accuracy eval gate for the {domain} vertical. Same harness as every
other vertical, different domain package imported.

The single case below passes against a freshly scaffolded vertical, where
can_handle() still returns 0.0 and therefore nothing claims the request. That
is a real assertion, not a placeholder: an agent that has not been taught what
it handles should decline, and __unhandled__ is what declining looks like.

Replace it as you implement can_handle() — one case per routing decision you
want held in place. The gate fails below {threshold:.0%} accuracy.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

import agents.{domain}.agent  # noqa: F401 — self-registers on import
import agents.{domain}.tools  # noqa: F401
from core.registry import AgentRegistry
from governance.eval_harness import RoutingTestCase, assert_eval_gate, run_routing_eval

THRESHOLD = {threshold}


def _state_for(text: str) -> dict:
    return {{
        "messages": [HumanMessage(content=text)],
        "current_agent": "supervisor",
        "routing_history": [],
        "pending_approval": None,
        "domain_context": {{}},
    }}


{upper}_ROUTING_CASES = [
    RoutingTestCase(
        description="a request no agent claims routes nowhere",
        state=_state_for("zzz unclaimed placeholder request zzz"),
        expected_agent="__unhandled__",
    ),
    # Add one RoutingTestCase per routing decision worth protecting, e.g.:
    # RoutingTestCase(
    #     description="...describe the intent being routed...",
    #     state=_state_for("a message a real user would send"),
    #     expected_agent="{domain}_agent",
    # ),
]


@pytest.fixture(autouse=True)
def _ensure_{domain}_registered():
    names = {{a.name for a in AgentRegistry.all()}}
    required = {{"{domain}_agent"}}
    assert required.issubset(names), f"Missing registered agents: {{required - names}}"


def test_{domain}_routing_accuracy_gate():
    result = run_routing_eval({upper}_ROUTING_CASES, threshold=THRESHOLD)
    assert_eval_gate(result, threshold=THRESHOLD)


def test_{domain}_routing_accuracy_is_reported():
    result = run_routing_eval({upper}_ROUTING_CASES, threshold=0.0)
    print(f"\\n{domain} routing accuracy: {{result.accuracy:.0%}} ({{result.correct}}/{{result.total}})")
    if result.failures:
        print("Failures:")
        for f in result.failures:
            print(f"  - {{f}}")
'''


# --------------------------------------------------------------------------
# steps
# --------------------------------------------------------------------------


def scaffold_package(domain: str, dry_run: bool) -> Path:
    target = REPO_ROOT / "agents" / domain
    if target.exists():
        raise ScaffoldError(
            f"agents/{domain}/ already exists. Delete it first, or pick another name."
        )
    if not TEMPLATE_DIR.is_dir():
        raise ScaffoldError(f"Template package missing at {TEMPLATE_DIR}")

    if dry_run:
        return target

    shutil.copytree(TEMPLATE_DIR, target)
    for py_file in sorted(target.glob("*.py")):
        text = rename_identifiers(py_file.read_text(), domain)
        if py_file.name in DOCSTRINGS:
            text = swap_module_docstring(
                text,
                DOCSTRINGS[py_file.name].format(domain=domain, cls=class_prefix(domain)),
            )
        py_file.write_text(text)
    return target


def scaffold_eval(domain: str, threshold: float, dry_run: bool) -> Path:
    target = REPO_ROOT / "tests" / "eval" / f"test_{domain}_decisions.py"
    if target.exists():
        raise ScaffoldError(f"{target.relative_to(REPO_ROOT)} already exists.")
    if not dry_run:
        target.write_text(
            EVAL_TEMPLATE.format(domain=domain, upper=domain.upper(), threshold=threshold)
        )
    return target


def register_boundary_token(domain: str, dry_run: bool) -> bool:
    """Add the domain to suspicious_tokens so the boundary test guards it too.

    Returns False if it was already listed. This is the step most easily
    forgotten by hand, and forgetting it means the new domain's name is the
    one name the boundary test does not check for in core/ and governance/.
    """
    text = BOUNDARY_TEST.read_text()
    match = re.search(r"suspicious_tokens = \[(.*?)\]", text, re.DOTALL)
    if match is None:
        raise ScaffoldError(
            f"Could not find suspicious_tokens in {BOUNDARY_TEST.relative_to(REPO_ROOT)} — "
            f"add \"{domain}\" to it by hand."
        )
    if f'"{domain}"' in match.group(1):
        return False
    if not dry_run:
        updated = match.group(0).replace("]", f', "{domain}"]', 1)
        BOUNDARY_TEST.write_text(text.replace(match.group(0), updated, 1))
    return True


def activate(domain: str, dry_run: bool) -> bool:
    """Point api/main.py at the new vertical. Opt-in: this decides which
    vertical the running app serves, which is not a scaffolder's call to make
    by default."""
    text = API_MAIN.read_text()
    pattern = re.compile(r"^import agents\.(\w+)\.(agent|tools).*$", re.MULTILINE)
    matches = pattern.findall(text)
    if not matches:
        raise ScaffoldError(
            f"No domain import found in {API_MAIN.relative_to(REPO_ROOT)} — swap it by hand."
        )
    current = matches[0][0]
    if current == domain:
        return False
    if not dry_run:
        API_MAIN.write_text(pattern.sub(lambda m: f"import agents.{domain}.{m.group(2)}  # noqa: F401", text))
    return True


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.new_vertical",
        description="Scaffold a new Switchboard domain vertical from agents/_template/.",
    )
    parser.add_argument("domain", help="package name for the vertical, e.g. clinic_ops")
    parser.add_argument(
        "--activate",
        action="store_true",
        help="also point api/main.py at the new vertical (replaces the current one)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="routing accuracy gate for the generated eval file (default: 0.8)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would be written without writing anything",
    )
    args = parser.parse_args(argv)
    domain = args.domain

    eval_file = REPO_ROOT / "tests" / "eval" / f"test_{domain}_decisions.py"
    # An existing package plus --activate means "make this the active vertical",
    # which is exactly what the next-steps hint below tells people to run after
    # scaffolding. Only refuse when there is nothing to do but overwrite.
    already_scaffolded = (REPO_ROOT / "agents" / domain).exists() and args.activate

    try:
        validate_domain(domain)
        if not already_scaffolded:
            scaffold_package(domain, args.dry_run)
            eval_file = scaffold_eval(domain, args.threshold, args.dry_run)
        token_added = register_boundary_token(domain, args.dry_run)
        activated = activate(domain, args.dry_run) if args.activate else False
    except ScaffoldError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    prefix = "would write" if args.dry_run else "wrote"
    if already_scaffolded:
        print(f"\nagents/{domain}/ already exists — activating it without rewriting anything")
    else:
        print(
            f"\n{prefix} agents/{domain}/  "
            f"({len(list(TEMPLATE_DIR.glob('*.py')))} files from _template)"
        )
        print(f"{prefix} {eval_file.relative_to(REPO_ROOT)}")
    if token_added:
        print(f"{prefix} \"{domain}\" into suspicious_tokens in {BOUNDARY_TEST.relative_to(REPO_ROOT)}")
    else:
        print(f'"{domain}" was already in suspicious_tokens — left alone')
    if args.activate:
        print(
            f"{prefix} the domain import in {API_MAIN.relative_to(REPO_ROOT)}"
            if activated
            else f"{API_MAIN.relative_to(REPO_ROOT)} already points at {domain} — left alone"
        )

    if args.dry_run:
        print("\nnothing was written (--dry-run).")
        return 0

    print(f"\nNext:")
    print(f"  1. Implement can_handle() and execute() in agents/{domain}/agent.py")
    print(f"     (can_handle returns 0.0 until you do, so nothing routes there yet)")
    print(f"  2. Add real routing cases to {eval_file.relative_to(REPO_ROOT)}")
    if not args.activate:
        print(f"  3. Point the app at it:  python -m scripts.new_vertical {domain} --activate")
        print(f"     or edit the two import lines in {API_MAIN.relative_to(REPO_ROOT)} by hand")
    print(f"\nVerify now:  python -m pytest tests/ -q")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
