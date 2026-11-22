"""Le cycle de développement (scripts/feature.sh, hooks) : hors-ligne, dans un dépôt jetable, avec un faux gh."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent

# Le faux gh lit les issues dans $FAKE_GH/<n>/{title,labels,state,body} et note chaque appel.
FAKE_GH = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_GH/calls"
case "$1 $2" in
  "issue view") cat "$FAKE_GH/$3/$5" ;;
  "issue create") echo "https://github.com/owner/repo/issues/99" ;;
esac
exit 0
"""

STORY = """**As a** musician in rehearsal, **I want** to loop the chorus, **so that** I can work on it.

## Today
The loop clicks at the wrap.

## Done when
- [ ] The loop wraps without a click
"""


def git(repo, *args, **kw):
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True, **kw).stdout.strip()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Un clone de travail avec son origin, les scripts du cycle, un check.sh qui passe, et un faux gh."""
    for key, value in {"NAME": "Test", "EMAIL": "test@example.invalid"}.items():
        monkeypatch.setenv(f"GIT_AUTHOR_{key}", value)
        monkeypatch.setenv(f"GIT_COMMITTER_{key}", value)
    monkeypatch.delenv("ARR_ALLOW_MAIN", raising=False)
    monkeypatch.delenv("ARR_ALLOW_ISSUE", raising=False)
    monkeypatch.delenv("ARR_ALLOW_NAMES", raising=False)
    library = tmp_path / "library"
    (library / "zorglub--hymne").mkdir(parents=True)
    (library / "zorglub--hymne/song.toml").write_text('title = "Hymne du Zorglub"\nartist = "Zorglub"\n')
    monkeypatch.setenv("ARR_LIBRARY", str(library))
    origin, work, bin_dir, gh = (tmp_path / d for d in ("origin.git", "work", "bin", "gh"))
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True)
    git(work, "symbolic-ref", "HEAD", "refs/heads/main")
    (work / "scripts").mkdir()
    for script in ("feature.sh", "install-hooks.sh", "check_names.py"):
        shutil.copy(ROOT / "scripts" / script, work / "scripts" / script)
    check = work / "scripts/check.sh"
    check.write_text('#!/usr/bin/env bash\necho check >> "$FAKE_GH/calls"\n')
    check.chmod(0o755)
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "init")
    git(work, "push", "-q", "origin", "main")
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "gh").chmod(0o755)
    gh.mkdir()
    (gh / "calls").touch()
    monkeypatch.setenv("FAKE_GH", str(gh))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    return work


def add_issue(repo, n, title, labels, body=STORY, state="OPEN"):
    d = Path(os.environ["FAKE_GH"]) / str(n)
    d.mkdir()
    for name, value in {"title": title, "labels": labels, "state": state, "body": body}.items():
        (d / name).write_text(value + "\n")


def feature(repo, *args):
    return subprocess.run([str(repo / "scripts/feature.sh"), *args], cwd=repo, capture_output=True, text=True)


def calls():
    return (Path(os.environ["FAKE_GH"]) / "calls").read_text()


# --- le style des issues


def test_a_story_in_the_musicians_words_is_created(repo, tmp_path):
    body = tmp_path / "body.md"
    body.write_text(STORY)
    framing = tmp_path / "framing.md"
    framing.write_text("Look at the loop in play.py.")
    result = feature(repo, "issue", "story", "Loop the chorus without a click", str(body), str(framing))
    assert result.returncode == 0, result.stderr
    assert "issue create --title Loop the chorus without a click --label story" in calls()
    assert "issue comment 99" in calls()


@pytest.mark.parametrize(
    ("kind", "title", "body", "reason"),
    [
        ("feature", "Loop the chorus", STORY, "type"),
        ("story", "play: loop the chorus", STORY, "préfixé"),
        ("story", "Loop the chorus", STORY.replace("## Today", "## Now"), "## Today"),
        ("story", "Loop the chorus", STORY.replace("- [ ]", "-"), "case à cocher"),
        ("story", "Loop the chorus", STORY + "\nSee src/arr/commands/play.py.\n", "chemin de source"),
        ("story", "Loop the chorus", STORY + "\nCall arr.audio.splice.\n", "chemin de source"),
        ("story", "Loop the chorus", STORY + "\n## Technical framing\n", "rubrique technique"),
    ],
)
def test_an_issue_out_of_style_is_refused(repo, tmp_path, kind, title, body, reason):
    path = tmp_path / "body.md"
    path.write_text(body)
    result = feature(repo, "issue", kind, title, str(path))
    assert result.returncode != 0
    assert reason in result.stderr
    assert "issue create" not in calls()


def test_commands_and_project_files_are_allowed_in_the_body(repo, tmp_path):
    path = tmp_path / "body.md"
    path.write_text(STORY + "\nWith `arr play -s chorus --loop`, the patch stored in `sheet.toml`.\n")
    assert feature(repo, "issue", "story", "Loop the chorus", str(path)).returncode == 0


def test_an_issue_to_refine_must_say_what_is_left_to_decide(repo, tmp_path):
    path = tmp_path / "body.md"
    path.write_text(STORY)
    refused = feature(repo, "issue", "--refine", "story", "Loop the chorus", str(path))
    assert refused.returncode != 0 and "To decide" in refused.stderr
    path.write_text(STORY + "\n## To decide\n- How long is the fade?\n")
    accepted = feature(repo, "issue", "--refine", "story", "Loop the chorus", str(path))
    assert accepted.returncode == 0, accepted.stderr
    assert "--label story,needs-refinement" in calls()


# --- démarrer une issue


def test_start_opens_a_branch_named_after_the_issue(repo):
    add_issue(repo, 12, "Loop the chorus without a click", "chore", body="## Why\nx\n\n## Done when\n- [ ] y\n")
    result = feature(repo, "start", "12")
    assert result.returncode == 0, result.stderr
    assert git(repo, "branch", "--show-current") == "chore/12-loop-the-chorus-without-a-click"


@pytest.mark.parametrize(("labels", "prefix"), [("story", "feat"), ("bug", "fix"), ("story,documentation", "docs")])
def test_the_branch_prefix_follows_the_label(repo, labels, prefix):
    body = "## What happens\nx\n\n## What should happen\ny\n" if labels == "bug" else STORY
    add_issue(repo, 7, "Loop the chorus", labels, body=body)
    assert feature(repo, "start", "7").returncode == 0
    assert git(repo, "branch", "--show-current") == f"{prefix}/7-loop-the-chorus"


def test_start_never_reuses_a_branch_name(repo):
    add_issue(repo, 12, "Loop the chorus", "story")
    git(repo, "branch", "feat/12-loop-the-chorus")
    assert feature(repo, "start", "12").returncode == 0
    assert git(repo, "branch", "--show-current") == "feat/12-loop-the-chorus-2"


@pytest.mark.parametrize(
    ("labels", "body", "reason"),
    [
        ("epic", "## Where we are\nx\n\n## Stories\n- [ ] #3\n", "épique"),
        ("story,needs-refinement", STORY + "\n## To decide\n- ?\n", "à cadrer"),
        ("story", "Just do it.", "réécrire l'issue"),
    ],
)
def test_start_refuses_an_issue_that_is_not_ready(repo, labels, body, reason):
    add_issue(repo, 5, "Loop the chorus", labels, body=body)
    result = feature(repo, "start", "5")
    assert result.returncode != 0
    assert reason in result.stderr
    assert git(repo, "branch", "--show-current") == "main"


def test_start_refuses_a_closed_issue_and_a_dirty_tree(repo):
    add_issue(repo, 5, "Loop the chorus", "story", state="CLOSED")
    assert "pas ouverte" in feature(repo, "start", "5").stderr
    (repo / "wip.txt").write_text("x")
    assert "non propre" in feature(repo, "start", "5").stderr


def test_pr_refuses_a_branch_without_an_issue(repo):
    git(repo, "checkout", "-q", "-b", "some-work")
    result = feature(repo, "pr")
    assert result.returncode != 0
    assert "attendu" in result.stderr


# --- les hooks


@pytest.fixture
def hooked(repo):
    subprocess.run([str(repo / "scripts/install-hooks.sh")], cwd=repo, check=True, capture_output=True)
    return repo


def commit(repo, message="change", env=None):
    (repo / "file.txt").write_text(message)
    git(repo, "add", "file.txt")
    return subprocess.run(
        ["git", "commit", "-q", "-m", message],
        cwd=repo,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def test_a_commit_on_main_is_refused_unless_asked(hooked):
    refused = commit(hooked)
    assert refused.returncode != 0
    assert "pas de commit direct sur main" in refused.stderr
    assert commit(hooked, "urgent", env={"ARR_ALLOW_MAIN": "1"}).returncode == 0


def test_a_push_to_main_is_refused(hooked):
    commit(hooked, "urgent", env={"ARR_ALLOW_MAIN": "1"})
    refused = subprocess.run(["git", "push", "-q", "origin", "main"], cwd=hooked, capture_output=True, text=True)
    assert refused.returncode != 0
    assert "pas de push direct sur main" in refused.stderr


def test_a_commit_on_an_issue_branch_runs_the_checks_and_cites_the_issue(hooked):
    git(hooked, "checkout", "-q", "-b", "feat/12-loop")
    assert commit(hooked, "Loop without a click\n\nCo-Authored-By: Someone <a@b.invalid>").returncode == 0
    message = git(hooked, "log", "-1", "--format=%B")
    assert message.index("Refs #12") < message.index("Co-Authored-By")
    assert "check" in calls()


def test_a_commit_naming_a_song_of_the_library_is_refused(hooked):
    git(hooked, "checkout", "-q", "-b", "feat/12-loop")
    refused = commit(hooked, "Exemple : hymne du zorglub")
    assert refused.returncode != 0
    assert "file.txt:1 : « hymne du zorglub » (title de zorglub--hymne)" in refused.stderr
    assert commit(hooked, "Exemple : hymne du zorglub", env={"ARR_ALLOW_NAMES": "1"}).returncode == 0
