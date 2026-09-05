"""The specification of the requested repair.

`test_a_reading_exactly_at_the_limit_is_not_an_alarm` FAILS against the shipped
code. That failure is the bug report: the fixture is delivered broken on
purpose, and a repair is correct exactly when this suite passes.
"""

import unittest

from pumpcheck import limits


class TestVibrationLimit(unittest.TestCase):
    def test_a_reading_above_the_limit_is_an_alarm(self):
        self.assertTrue(limits.vibration_alarm(7.9))

    def test_a_reading_below_the_limit_is_not_an_alarm(self):
        self.assertFalse(limits.vibration_alarm(4.1))

    def test_a_reading_exactly_at_the_limit_is_not_an_alarm(self):
        """SOP-MECH-014 2.1 says "shall not exceed", so 7.1 is in
        specification. The shipped `>=` reports a false alarm here."""
        self.assertFalse(limits.vibration_alarm(7.1))


class TestBearingTemperature(unittest.TestCase):
    def test_above_the_limit_is_an_overtemperature(self):
        self.assertTrue(limits.bearing_overtemperature(81.0))

    def test_exactly_at_the_limit_is_not(self):
        self.assertFalse(limits.bearing_overtemperature(80.0))

    def test_within_limit_is_not(self):
        self.assertFalse(limits.bearing_overtemperature(71.0))


if __name__ == "__main__":
    unittest.main()
