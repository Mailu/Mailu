import importlib.util
from pathlib import Path
import re
import sys
import tempfile
import types
from unittest import TestCase, main
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "core/dovecot"))

# The host-side compose test runner does not install Mailu's base-image
# dependencies. Stub the shared helpers needed to import the Dovecot scripts.
socrate = types.ModuleType("socrate")
system = types.ModuleType("socrate.system")
system.mailbox_shard = lambda _address: "test"


def parse_bool(value, default=None):
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


system.parse_bool = parse_bool
socrate.system = system
sys.modules["socrate"] = socrate
sys.modules["socrate.system"] = system
# The mailbox helper only uses the standard library; load the real module
# instead of hiding it behind the minimal socrate.system stub.
mailbox_spec = importlib.util.spec_from_file_location(
    "socrate.mailbox", ROOT / "core/base/libs/socrate/socrate/mailbox.py"
)
mailbox = importlib.util.module_from_spec(mailbox_spec)
mailbox_spec.loader.exec_module(mailbox)
sys.modules["socrate.mailbox"] = mailbox
socrate.mailbox = mailbox


def load_script(name):
    path = ROOT / "core/dovecot" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration = load_script("migrate_mail")
rebuild = load_script("rebuild_fts")


class DovecotMigrationTests(TestCase):
    def test_dns_client_socket_is_available_inside_and_outside_mail_chroot(self):
        config = (ROOT / "core/dovecot/conf/dovecot.conf").read_text()
        self.assertIn(
            "dns_client_socket_path = dns-client",
            config,
        )
        service = re.search(r"service dns-client\s*\{(.*?)\n\}", config, re.DOTALL).group(1)

        self.assertRegex(
            service,
            r"unix_listener dns-client\s*\{"
            r"\s*path = dns-client"
            r"\s*group = dovecot\s*mode = 0660\s*type = dns-client",
        )
        self.assertRegex(
            service,
            r"unix_listener dns-client-chroot\s*\{"
            r"\s*path = /mail/run/dovecot/dns-client"
            r"\s*group = dovecot-proxy\s*mode = 0660\s*type = dns-client",
        )

    def test_normalize_message_adds_physical_and_virtual_sizes(self):
        with tempfile.TemporaryDirectory() as directory:
            message = Path(directory) / "123.host:2,RS"
            message.write_bytes(b"Subject: test\n\nbody\n")

            migration.normalize_message(str(message))

            normalized = Path(directory) / "123.host,S=20,W=23:2,RS"
            self.assertEqual(normalized.read_bytes(), b"Subject: test\n\nbody\n")

    def test_legacy_maildir_is_detected_but_unrecognized_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy = Path(directory) / "alice@example.org"
            for name in ("cur", "new", "tmp"):
                (legacy / name).mkdir(parents=True)

            unrelated = Path(directory) / "old-mail-backup"
            unrelated.mkdir()
            (unrelated / "cur").mkdir()

            self.assertEqual(
                migration.staged_legacy_mailboxes(directory),
                {"alice@example.org": str(legacy)},
            )

    def test_fts_language_change_queues_rebuild_without_deleting_old_indexes(self):
        with tempfile.TemporaryDirectory() as directory:
            mail = Path(directory) / "example.test/alice/mail"
            index = mail / "INBOX/xapian-indexes"
            index.mkdir(parents=True)
            config_file = Path(directory) / ".fts-config"
            config_file.write_text("en\n")
            pending = Path(directory) / ".fts-rebuild-pending"

            with patch.object(migration, "FTS_CONFIG", str(config_file)):
                with patch.object(migration, "FTS_MARKER", str(pending)):
                    with patch.dict("os.environ", {"FULL_TEXT_SEARCH": "fr"}):
                        migration.update_fts_indexes()

            self.assertTrue(index.is_dir())
            self.assertEqual(pending.read_text(), "pending\n")
            self.assertEqual(config_file.read_text(), "fr\n")

    def test_index_rebuild_queue_persists_remaining_mailboxes(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = Path(directory) / ".fts-rebuild-pending"
            emails = ["alice@example.test", "bob@example.test"]
            queue.write_text("pending\n")
            self.assertEqual(rebuild.read_mailbox_queue(queue, emails), set(emails))

            rebuild.write_mailbox_queue(queue, {"bob@example.test"})

            self.assertEqual(
                rebuild.read_mailbox_queue(queue, emails),
                {"bob@example.test"},
            )


if __name__ == "__main__":
    main()
