"""Version labels, maturity and the one ordering key.

    python3 -m unittest backend.coordinator.test_release -v

The Debian comparisons run the real `dpkg --compare-versions` and are skipped
where dpkg is not installed (they run on the Ubuntu build host and in CI).
"""

from __future__ import annotations

import shutil
import subprocess
import unittest

from backend.coordinator import release


class TestLabels(unittest.TestCase):
    def test_labels_name_their_channel_and_maturity(self):
        cases = {"0.1.0-internal.6": ("internal", None),
                 "0.1.0-preview.2": ("beta", "preview"),
                 "0.1.0-beta.1": ("beta", "accepted"),
                 "0.1.0": ("beta", "final")}
        for text, (channel, maturity) in cases.items():
            with self.subTest(text=text):
                label = release.parse(text)
                self.assertEqual((label.channel, label.maturity), (channel, maturity))
                self.assertEqual(str(label), text)

    def test_malformed_labels_are_refused(self):
        for text in ("latest", "0.1", "0.1.0-rc.1", "0.1.0-beta.0", "0.1.0-beta",
                     "v0.1.0", "0.1.0-preview.01", " 0.1.0"):
            with self.subTest(text=text), self.assertRaises(release.LabelError):
                release.parse(text)

    def test_a_label_must_agree_with_its_channel_and_maturity(self):
        release.check_identity("0.1.0-preview.1", "beta", "preview")
        release.check_identity("0.1.0-internal.3", "internal", None)
        for args in (("0.1.0-preview.1", "beta", "accepted"),
                     ("0.1.0-beta.1", "beta", "preview"),
                     ("0.1.0-internal.1", "beta", None),
                     ("0.1.0-preview.1", "internal", None),
                     ("0.1.0-internal.1", "internal", "preview"),
                     ("0.1.0", "beta", "accepted")):
            with self.subTest(args=args), self.assertRaises(release.LabelError):
                release.check_identity(*args)


class TestOrder(unittest.TestCase):
    def test_numeric_version_first_then_maturity_then_number(self):
        order = ["0.1.0-preview.1", "0.1.0-preview.2", "0.1.0-preview.10",
                 "0.1.0-beta.1", "0.1.0-beta.5", "0.1.0", "0.1.1-preview.1",
                 "0.1.1-beta.1", "0.2.0-preview.1", "1.0.0"]
        shuffled = list(reversed(order))
        self.assertEqual(sorted(shuffled, key=release.key), order)
        self.assertGreater(release.key("0.1.1-preview.1"), release.key("0.1.0-beta.5"))

    def test_internal_labels_keep_their_existing_order(self):
        order = ["0.1.0-internal.1", "0.1.0-internal.2", "0.1.0-internal.10",
                 "0.1.1-internal.1"]
        self.assertEqual(sorted(reversed(order), key=release.key), order)

    def test_debian_versions_carry_the_rank_as_a_number(self):
        self.assertEqual(release.parse("0.1.0-preview.3").debian(), "0.1.0~1.3")
        self.assertEqual(release.parse("0.1.0-beta.2").debian(), "0.1.0~2.2")
        self.assertEqual(release.parse("0.1.0").debian(), "0.1.0")
        self.assertEqual(release.parse("0.1.0-internal.6").debian(), "0.1.0~internal.6")
        self.assertEqual(release.parse("0.1.0-beta.2").windows(14), "0.1.0.14")

    @unittest.skipUnless(shutil.which("dpkg"), "dpkg is not installed here")
    def test_dpkg_orders_debian_versions_exactly_like_the_key(self):
        order = ["0.1.0-preview.1", "0.1.0-preview.2", "0.1.0-preview.10",
                 "0.1.0-beta.1", "0.1.0-beta.5", "0.1.0", "0.1.1-preview.1",
                 "0.1.1-beta.1", "1.0.0"]
        for lower, higher in zip(order, order[1:]):
            with self.subTest(lower=lower, higher=higher):
                result = subprocess.run(
                    ["dpkg", "--compare-versions", release.parse(lower).debian(), "lt",
                     release.parse(higher).debian()], check=False)
                self.assertEqual(result.returncode, 0)


class TestWhoIsOffered(unittest.TestCase):
    def test_preview_installs_take_previews_and_later_accepted_builds(self):
        self.assertTrue(release.offered_to("preview", "preview"))
        self.assertTrue(release.offered_to("preview", "accepted"))
        self.assertTrue(release.offered_to("preview", "final"))
        self.assertEqual(release.pointers_for("preview"),
                         ("latest.json", "latest-preview.json"))

    def test_accepted_installs_never_take_a_preview(self):
        for own in ("accepted", "final"):
            with self.subTest(own=own):
                self.assertFalse(release.offered_to(own, "preview"))
                self.assertTrue(release.offered_to(own, "accepted"))
                self.assertEqual(release.pointers_for(own), ("latest.json",))

    def test_internal_builds_only_take_internal_builds(self):
        self.assertTrue(release.offered_to(None, None))
        self.assertFalse(release.offered_to(None, "preview"))
        self.assertFalse(release.offered_to("preview", None))

    def test_a_pointer_names_only_its_own_maturity(self):
        self.assertTrue(release.pointer_allows("latest-preview.json", "preview", "beta"))
        self.assertFalse(release.pointer_allows("latest.json", "preview", "beta"))
        self.assertFalse(release.pointer_allows("latest-preview.json", "accepted", "beta"))
        self.assertTrue(release.pointer_allows("latest.json", "final", "beta"))
        self.assertTrue(release.pointer_allows("latest.json", None, "internal"))
        self.assertFalse(release.pointer_allows("latest-preview.json", None, "internal"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
