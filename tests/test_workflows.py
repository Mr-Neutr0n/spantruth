"""The workflows refer to things that exist, so a CI file cannot break without a test failing."""

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((REPO / ".github" / "workflows").glob("*.yml"))


def local_actions() -> list[tuple[str, str]]:
    found = []
    for path in WORKFLOWS:
        for job in yaml.safe_load(path.read_text())["jobs"].values():
            for step in job.get("steps", []):
                uses = step.get("uses", "")
                if uses.startswith(("./", "$/")):
                    found.append((path.name, uses))
    return found


def test_the_workflows_parse_and_use_the_local_action():
    assert len(WORKFLOWS) >= 4
    assert ("ci.yml", "$/") in local_actions()


def test_every_local_action_a_workflow_uses_exists():
    # `$/` is GitHub's self-repository syntax (July 2026): this repository at the workflow commit.
    for workflow, uses in local_actions():
        directory = REPO / uses[2:]
        assert (directory / "action.yml").is_file(), f"{workflow}: {uses}"
