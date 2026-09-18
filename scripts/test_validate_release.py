import json
import shutil
import tempfile
import unittest
from pathlib import Path

from validate_release import ROOT, validate


class PackageValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "catalog"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__", ".git"))
        self.plugin = self.root / "plugins/ski-macro-assistant"

    def change_json(self, path, edit):
        data = json.loads(path.read_text())
        edit(data)
        path.write_text(json.dumps(data))

    def rejected(self):
        with self.assertRaises(ValueError):
            validate(self.root)

    def test_valid_package(self):
        self.assertRegex(validate(self.root), r"^\d+\.\d+\.\d+$")

    def test_wrong_workspace(self):
        self.change_json(self.root / ".agents/plugins/marketplace.json",
                         lambda d: d["plugins"][0].update(pluginId="different-workspace"))
        self.rejected()

    def test_path_escape(self):
        self.change_json(self.root / ".agents/plugins/marketplace.json",
                         lambda d: d["plugins"][0]["source"].update(path="../elsewhere"))
        self.rejected()

    def test_version_mismatch(self):
        self.change_json(self.plugin / ".codex-plugin/plugin.json", lambda d: d.update(version="99.0.0"))
        self.rejected()

    def test_inline_mcp_rejected(self):
        self.change_json(self.plugin / ".codex-plugin/plugin.json", lambda d: d.update(mcpServers={}))
        self.rejected()

    def test_extra_file_rejected(self):
        (self.plugin / "mcp.json").write_text("{}")
        self.rejected()

    def test_broken_reference(self):
        (self.plugin / "skills/macro-work-assistant/references/contract-selection.md").unlink()
        self.rejected()

    def test_symlink_rejected(self):
        (self.plugin / "outside.md").symlink_to(self.root / "README.md")
        self.rejected()


if __name__ == "__main__":
    unittest.main()
