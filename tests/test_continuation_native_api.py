"""Native settings are fresh, separate observations on scoped REST records."""

import json
from unittest.mock import patch

from test_continuation_http import RequestCase


class NativeApiTests(RequestCase):
    def test_scoped_list_detail_and_search_observe_settings_without_toggling(self):
        home = self.root / "home"
        skill = home / ".claude/skills/native-demo"
        skill.mkdir(parents=True)
        document = b"---\nname: native-demo\ndescription: Use native demo when testing\n---\nbody\n"
        (skill / "SKILL.md").write_bytes(document)
        config = home / ".claude/settings.json"
        config.write_text(json.dumps({"skillOverrides": {"native-demo": "off"}, "secret": "private-value"}))
        with patch("skillsmgr.scopes._cwd", return_value=self.root / "project"):
            for path in ("/api/skills?scope=claude-code", "/api/skills/native-demo?scope=claude-code",
                         "/api/search?q=native-demo&scope=claude-code"):
                status, payload = self.request("GET", path)
                self.assertEqual(status, 200)
                row = payload[0] if isinstance(payload, list) else payload
                self.assertEqual(row["native_state"]["observed_setting"], "off")
                self.assertEqual(row["native_state"]["effective_state"], "unknown")
                self.assertFalse(row["disabled"])
                self.assertNotIn("private-value", str(payload))
            config.write_text(json.dumps({"skillOverrides": {"native-demo": "name-only"}}))
            _, row = self.request("GET", "/api/skills/native-demo?scope=claude-code")
            self.assertEqual(row["native_state"]["observed_setting"], "name-only")
        self.assertEqual((skill / "SKILL.md").read_bytes(), document)
        self.assertFalse((skill / "SKILL.md.disabled").exists())
