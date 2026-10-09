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
                 "0.1.0-beta.1": ("beta", "beta"),
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
        for args in (("0.1.0-preview.1", "beta", "beta"),
                     ("0.1.0-beta.1", "beta", "preview"),
                     ("0.1.0-internal.1", "beta", None),
                     ("0.1.0-preview.1", "internal", None),
                     ("0.1.0-internal.1", "internal", "preview"),
                     ("0.1.0", "beta", "beta")):
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
    def test_preview_installs_take_previews_and_later_beta_builds(self):
        self.assertTrue(release.offered_to("preview", "preview"))
        self.assertTrue(release.offered_to("preview", "beta"))
        self.assertTrue(release.offered_to("preview", "final"))
        self.assertEqual(release.pointers_for("preview"),
                         ("latest.json", "latest-preview.json"))

    def test_beta_installs_never_take_a_preview(self):
        for own in ("beta", "final"):
            with self.subTest(own=own):
                self.assertFalse(release.offered_to(own, "preview"))
                self.assertTrue(release.offered_to(own, "beta"))
                self.assertEqual(release.pointers_for(own), ("latest.json",))

    def test_internal_builds_only_take_internal_builds(self):
        self.assertTrue(release.offered_to(None, None))
        self.assertFalse(release.offered_to(None, "preview"))
        self.assertFalse(release.offered_to("preview", None))

    def test_a_pointer_names_only_its_own_maturity(self):
        self.assertTrue(release.pointer_allows("latest-preview.json", "preview", "beta"))
        self.assertFalse(release.pointer_allows("latest.json", "preview", "beta"))
        self.assertFalse(release.pointer_allows("latest-preview.json", "beta", "beta"))
        self.assertTrue(release.pointer_allows("latest.json", "final", "beta"))
        self.assertTrue(release.pointer_allows("latest.json", None, "internal"))
        self.assertFalse(release.pointer_allows("latest-preview.json", None, "internal"))



class TestBetaIdentityAndNames(unittest.TestCase):
    def test_a_beta_label_is_the_public_beta_not_an_accepted_release(self):
        # The maturity of `-beta.N` names the release class only; "accepted"
        # is not a maturity any more, so nothing can infer device acceptance
        # from a version label.
        self.assertEqual(release.parse("0.1.0-beta.1").maturity, "beta")
        self.assertNotIn("accepted", release.MATURITIES)
        with self.assertRaises(release.LabelError):
            release.check_identity("0.1.0-beta.1", "beta", "accepted")

    def test_preview_and_internal_identity_and_order_are_unchanged(self):
        self.assertEqual(release.parse("0.1.0-preview.2").maturity, "preview")
        self.assertEqual(release.parse("0.1.0-internal.6").maturity, None)
        self.assertEqual(release.parse("0.1.0-internal.6").debian(), "0.1.0~internal.6")
        self.assertLess(release.key("0.1.0-preview.9"), release.key("0.1.0-beta.1"))
        self.assertLess(release.key("0.1.0-beta.9"), release.key("0.1.0"))

    def test_public_file_names_are_plain_and_internal_names_are_unchanged(self):
        self.assertEqual(release.asset_name("0.1.0-beta.1", "linux-x64", "deb"),
                         "refinix_0.1.0-beta.1_amd64.deb")
        self.assertEqual(release.asset_name("0.1.0-preview.3", "linux-x64", "deb"),
                         "refinix_0.1.0-preview.3_amd64.deb")
        self.assertEqual(release.asset_name("0.1.0-internal.6", "linux-x64", "deb"),
                         "refinix_0.1.0~internal.6_amd64.deb")
        for version in ("0.1.0-beta.1", "0.1.0"):
            for lane, fmt in (("macos-arm64", "zip"), ("windows-x64", "exe"),
                              ("linux-x64", "deb")):
                name = release.asset_name(version, lane, fmt)
                with self.subTest(name=name):
                    self.assertRegex(name, r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
                    self.assertEqual(release.package_target(version, lane, fmt),
                                     f"v{version}/{name}")
            self.assertRegex(release.dmg_name(version), r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
