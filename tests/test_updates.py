import importlib.util
import json
import shutil
import stat
import zipfile
from pathlib import Path

import pytest

from meta_ads_manager import specialist
from meta_ads_manager.errors import AppError
from meta_ads_manager.workspace import run

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("workbench_update_test", ROOT / "update.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


def release(path, ver="0.6.0", extra=None):
    files = {
        ".gitignore": "*\n",
        "README.md": f"Version {ver}\n",
        "pyproject.toml": f'[project]\nname="example"\nversion="{ver}"\n',
        "adapters/antigravity.md": "Read AGENTS.md",
        "src/tool.py": ver,
    }
    files.update(extra or {})
    for name, content in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    (path / "release-files.json").write_text(json.dumps({"files": list(files)}))
    hashes = {n: updater.digest(path / n) for n in [*files, "release-files.json"]}
    (path / "RELEASE-MANIFEST.json").write_text(json.dumps({"version": ver, "sha256": hashes}))
    return path


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "client"
    root.mkdir()
    (root / "workspace.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "kind": "operator_workspace",
                "workspace_id": "w1",
                "client_id": "test",
                "name": "Test",
                "release_version": "0.5.0",
            }
        )
    )
    old = release(tmp_path / "old", "0.5.0", {"src/obsolete.py": "old"})
    _, mapping = updater.incoming_files(old)
    for name, path in mapping.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, root / name)
    (root / ".gitignore").write_text("CUSTOM IGNORE\n*\n")
    for name in [
        "context/materials/note.md",
        "data/client.sqlite3",
        "config/local/other.json",
        "secrets/synthetic.txt",
        "reports/report.pdf",
        "specialist/local.md",
        "specialist.json",
        "skills/my-custom/SKILL.md",
        ".claude/settings.json",
    ]:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("SYNTHETIC USER DATA")
    updater.save(root / updater.STATE, updater.installed_state(root, old))
    monkeypatch.chdir(root)
    return root, old


def protected(root):
    names = [
        "workspace.json",
        ".gitignore",
        "context/materials/note.md",
        "data/client.sqlite3",
        "config/local/other.json",
        "secrets/synthetic.txt",
        "reports/report.pdf",
        "specialist/local.md",
        "specialist.json",
        "skills/my-custom/SKILL.md",
        ".claude/settings.json",
    ]
    return {n: (root / n).read_bytes() for n in names}


def apply(root, source, **kw):
    return updater.apply(
        root, source, prepare=lambda *args: ".venv/bin/python", check=lambda *args: None, **kw
    )


def test_update_preserves_private_and_custom_files_and_removes_owned_obsolete(workspace, tmp_path):
    root, _ = workspace
    private = protected(root)
    new = release(tmp_path / "new")
    result = apply(root, new)
    assert result["status"] == "updated"
    assert (root / "src/tool.py").read_text() == "0.6.0"
    assert not (root / "src/obsolete.py").exists()
    assert protected(root) == private
    assert updater.load(root / updater.STATE)["version"] == "0.6.0"
    assert apply(root, new)["status"] == "up_to_date"


@pytest.mark.parametrize(
    "name", ["README.md", "src/tool.py", "src/obsolete.py", ".agents/rules/meta-ads.md"]
)
def test_modified_owned_files_stop_before_changes(workspace, tmp_path, name):
    root, _ = workspace
    (root / name).write_text("LOCAL EDIT")
    new = release(tmp_path / "new")
    preview = updater.plan(root, new)
    assert name in preview["conflicts"]
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="Lokalne"):
        apply(root, new)
    assert all(p.read_bytes() == content for p, content in before.items())


def test_new_release_cannot_overwrite_unknown_local_file(workspace, tmp_path):
    root, _ = workspace
    new = release(tmp_path / "new", extra={"skills/my-custom/SKILL.md": "new"})
    assert "skills/my-custom/SKILL.md" in updater.plan(root, new)["conflicts"]
    with pytest.raises(ValueError):
        apply(root, new)


def test_failure_rolls_back_code_state_and_preserves_private_files(workspace, tmp_path):
    root, _ = workspace
    new = release(tmp_path / "new", extra={"src/new.py": "new"})
    private = protected(root)
    state = (root / updater.STATE).read_bytes()

    def failed(*args):
        raise ValueError("health failed")

    with pytest.raises(ValueError, match="health failed"):
        updater.apply(root, new, prepare=lambda *args: ".venv/bin/python", check=failed)
    assert (root / updater.STATE).read_bytes() == state
    assert (root / "src/tool.py").read_text() == "0.5.0"
    assert (root / "src/obsolete.py").read_text() == "old"
    assert not (root / "src/new.py").exists()
    assert not (root / updater.PENDING).exists()
    assert protected(root) == private


def test_interrupted_update_blocks_cli_and_can_be_recovered(workspace, tmp_path, capsys):
    root, _ = workspace
    new = release(tmp_path / "new")

    def interrupted(*args):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        updater.apply(root, new, prepare=lambda *args: ".venv/bin/python", check=interrupted)
    assert (root / updater.PENDING).exists()
    assert run(["status"]) == 2
    assert "WORKSPACE_MAINTENANCE" in capsys.readouterr().out
    assert updater.rollback(root)["status"] == "rolled_back"
    assert (root / "src/tool.py").read_text() == "0.5.0"


def test_rollback_will_not_erase_edits_after_interruption(workspace, tmp_path):
    root, _ = workspace
    new = release(tmp_path / "new")

    def interrupted(*args):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        updater.apply(root, new, prepare=lambda *args: ".venv/bin/python", check=interrupted)
    (root / "src/tool.py").write_text("NEW LOCAL EDIT")
    with pytest.raises(ValueError, match="zmieniono"):
        updater.rollback(root)
    assert (root / "src/tool.py").read_text() == "NEW LOCAL EDIT"
    assert (root / updater.PENDING).exists()


def test_old_installation_uses_verified_original_baseline(workspace, tmp_path):
    root, old = workspace
    (root / updater.STATE).unlink()
    (root / "RELEASE-MANIFEST.json").unlink()
    new = release(tmp_path / "new")
    with pytest.raises(ValueError, match="Starsza instalacja"):
        updater.plan(root, new)
    assert updater.plan(root, new, old)["conflicts"] == []
    assert apply(root, new, baseline=old)["status"] == "updated"


@pytest.mark.parametrize(
    "path",
    [
        "context/materials/a.md",
        "specialist/personal.md",
        "specialist.json",
        "workspace.json",
        "config/local/c.json",
        "../README.md",
        "src/../../client.txt",
        "/tmp/file",
        "src/.hidden/a.py",
        "src\\file.py",
    ],
)
def test_release_cannot_claim_private_paths(tmp_path, path):
    with pytest.raises(ValueError):
        updater.validate_name(path)


def test_invalid_hash_symlink_downgrade_and_lock(workspace, tmp_path, capsys):
    root, _ = workspace
    new = release(tmp_path / "new")
    (new / "src/tool.py").write_text("tamper")
    with pytest.raises(ValueError):
        updater.plan(root, new)
    new = release(tmp_path / "new")
    (root / "src/tool.py").unlink()
    (root / "src/tool.py").symlink_to(new / "src/tool.py")
    with pytest.raises(ValueError):
        updater.plan(root, new)
    with updater.exclusive(root):
        assert run(["status"]) == 2
        assert "WORKSPACE_MAINTENANCE" in capsys.readouterr().out
    (root / "src/tool.py").unlink()
    (root / "src/tool.py").write_text("0.5.0")
    older = release(tmp_path / "older", "0.4.0")
    with pytest.raises(ValueError, match="obniżenia"):
        updater.plan(root, older)


def test_local_edit_during_environment_build_is_not_overwritten(workspace, tmp_path):
    root, _ = workspace
    new = release(tmp_path / "new")

    def prepare(*args):
        (root / "README.md").write_text("EDIT DURING BUILD")
        return ".venv/bin/python"

    with pytest.raises(ValueError, match="Stan plików"):
        updater.apply(root, new, prepare=prepare)
    assert (root / "README.md").read_text() == "EDIT DURING BUILD"
    assert (root / "src/tool.py").read_text() == "0.5.0"


@pytest.mark.parametrize(
    "entry", ["meta-ads-workbench/../escape", "meta-ads-workbench/context/stolen.md"]
)
def test_archive_traversal_and_private_paths(tmp_path, entry):
    archive = tmp_path / "meta-ads-workbench.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr(entry, "x")
    checksum = archive.with_suffix(".zip.sha256")
    checksum.write_text(f"{updater.digest(archive)}  {archive.name}\n")
    with pytest.raises(ValueError):
        updater.unpack(archive, checksum, tmp_path / "unpack")


def test_archive_symlink_and_wrong_checksum(tmp_path):
    archive = tmp_path / "meta-ads-workbench.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        info = zipfile.ZipInfo("meta-ads-workbench/src/link.py")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        zipped.writestr(info, "/elsewhere")
    checksum = archive.with_suffix(".zip.sha256")
    checksum.write_text(f"{updater.digest(archive)}  {archive.name}\n")
    with pytest.raises(ValueError):
        updater.unpack(archive, checksum, tmp_path / "unpack")
    checksum.write_text("0" * 64 + "  " + archive.name)
    with pytest.raises(ValueError):
        updater.unpack(archive, checksum, tmp_path / "unpack")


@pytest.fixture
def client(tmp_path, monkeypatch):
    root = tmp_path / "a"
    root.mkdir()
    (root / "workspace.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "kind": "operator_workspace",
                "client_id": "a",
            }
        )
    )
    monkeypatch.chdir(root)
    return root


def test_profile_shared_between_clients_and_versions_preserved(client, tmp_path):
    directory = tmp_path / "specialist"
    specialist.init(client, directory, "anna", "Anna")
    source = tmp_path / "method.md"
    source.write_text("Testuj jedną hipotezę naraz.")
    row = specialist.add(client, source, "Testy", "experiments")
    assert specialist.listing(client)["items"] == []
    specialist.status(client, row["id"], 1, "active", "Moja wytyczna")
    assert specialist.read(client, row["id"])["text"] == source.read_text()
    other = tmp_path / "b"
    other.mkdir()
    (other / "workspace.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "kind": "operator_workspace",
                "client_id": "b",
            }
        )
    )
    specialist.attach(other, directory)
    assert specialist.listing(client) == specialist.listing(other)
    source.write_text("Testuj hipotezę z wcześniej ustalonym kryterium sukcesu.")
    specialist.add(client, source, "Testy", "experiments", row["id"])
    assert specialist.read(other, row["id"])["revision"] == 1
    specialist.status(client, row["id"], 2, "active", "Stosuj tę wersję")
    assert specialist.read(other, row["id"])["revision"] == 2
    assert specialist.read(other, row["id"], 1)["status"] == "retired"
    assert specialist.read(other, row["id"], 1)["text"] == "Testuj jedną hipotezę naraz."
    assert len(specialist.listing(client, history=True)["items"]) == 2


def test_profile_integrity_and_client_separation(client, tmp_path):
    specialist.init(client, client / "specialist", "anna", "Anna")
    source = tmp_path / "method.md"
    source.write_text("Moja metoda")
    row = specialist.add(client, source, "Metoda", "test")
    specialist.status(client, row["id"], 1, "active", "Tak")
    (client / "specialist" / row["file"]).write_text("Tamper")
    with pytest.raises(AppError):
        specialist.listing(client)
    other = tmp_path / "b"
    other.mkdir()
    shutil.copy2(client / "workspace.json", other / "workspace.json")
    with pytest.raises(AppError):
        specialist.attach(other, client / "specialist")
    private = client / "context/note.md"
    private.parent.mkdir()
    private.write_text("Dane klienta")
    with pytest.raises(AppError):
        specialist.add(client, private, "Klient", "test")


def test_specialist_cli_and_no_profile_is_optional(client, tmp_path, capsys):
    assert run(["specialist", "list"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["attached"] is False
    assert (
        run(
            [
                "specialist",
                "init",
                "--directory",
                str(tmp_path / "profile"),
                "--id",
                "anna",
                "--name",
                "Anna",
            ]
        )
        == 0
    )
    source = tmp_path / "method.md"
    source.write_text("Moja metoda")
    capsys.readouterr()
    assert (
        run(["specialist", "add", "--file", str(source), "--title", "Metoda", "--topic", "test"])
        == 0
    )
    row = json.loads(capsys.readouterr().out)["data"]
    assert (
        run(
            [
                "specialist",
                "status",
                "--id",
                row["id"],
                "--revision",
                "1",
                "--status",
                "active",
                "--reason",
                "Stosuj moją metodę",
            ]
        )
        == 0
    )
    assert run(["specialist", "read", "--id", row["id"]]) == 0
