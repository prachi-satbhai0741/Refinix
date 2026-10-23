"""Offline checks for context selection. No server, model or network."""

import unittest

from backend.coordinator import context


def msgs(*specs):
    """specs: (role, character_count) pairs, oldest first."""
    return [{"message_id": f"m{i}", "role": r, "text": "x" * n}
            for i, (r, n) in enumerate(specs)]


class TestBudget(unittest.TestCase):
    def test_output_allowance_is_subtracted(self):
        # num_predict is an output maximum the runtime does not deduct for us.
        self.assertLess(context.input_budget(8192, 2048),
                        context.input_budget(8192, 512))

    def test_budget_never_negative(self):
        self.assertEqual(context.input_budget(512, 4096), 0)

    def test_estimate_is_labelled_an_estimate(self):
        self.assertIn("estimate", context.Selection().counting_method)

    def test_built_messages_include_role_overhead(self):
        messages = [{"role": "system", "content": "rule"},
                    {"role": "user", "content": "question"}]
        expected = sum(context.estimate_tokens(item["content"])
                       + context.PER_MESSAGE_OVERHEAD for item in messages)
        self.assertEqual(context.estimate_messages(messages), expected)


class TestSelection(unittest.TestCase):
    def test_short_conversation_is_sent_whole(self):
        conv = msgs(("user", 40), ("assistant", 40), ("user", 40))
        payload, sel = context.select(conv, window=8192, output_allowance=2048)
        self.assertEqual(len(payload), 3)
        self.assertEqual(sel.omitted_count, 0)
        self.assertIsNone(sel.note)

    def test_long_conversation_drops_oldest_and_says_so(self):
        conv = msgs(*[("user" if i % 2 == 0 else "assistant", 4000) for i in range(12)])
        payload, sel = context.select(conv, window=8192, output_allowance=2048)
        self.assertGreater(sel.omitted_count, 0)
        self.assertLessEqual(sel.estimated_input_tokens, sel.input_budget_tokens)
        self.assertIn("remain in your chat", sel.note)
        # The oldest goes first; the newest is always present.
        self.assertEqual(sel.omitted_ids[0], "m0")
        self.assertEqual(payload[-1]["content"], conv[-1]["text"])

    def test_newest_message_is_never_dropped(self):
        conv = msgs(("user", 9000), ("assistant", 9000), ("user", 300))
        payload, sel = context.select(conv, window=8192, output_allowance=2048)
        self.assertEqual(payload[-1]["content"], conv[-1]["text"])
        self.assertTrue(sel.newest_fits)

    def test_oversized_newest_is_reported_not_chopped(self):
        conv = msgs(("user", 200_000))
        payload, sel = context.select(conv, window=8192, output_allowance=2048)
        self.assertFalse(sel.newest_fits)
        self.assertEqual(payload[0]["content"], conv[0]["text"],
                         "the message is passed through intact, never truncated")
        self.assertIn("Shorten it or split it", sel.note)

    def test_no_orphan_assistant_reply(self):
        """An assistant reply is never sent without the message it answered."""
        conv = msgs(*[("user" if i % 2 == 0 else "assistant", 3600) for i in range(10)])
        payload, _ = context.select(conv, window=8192, output_allowance=2048)
        if payload and payload[0]["role"] == "assistant":
            self.fail("selection began with an orphan assistant reply")

    def test_a_leading_system_rule_is_retained_and_counted(self):
        conv = [{"message_id": "system", "role": "system", "text": "rule" * 20},
                *msgs(("user", 200))]
        payload, selection = context.select(
            conv, window=8192, output_allowance=2048)
        self.assertEqual(payload[0]["role"], "system")
        self.assertIn("system", selection.included_ids)
        expected = sum(context.estimate_tokens(item["text"])
                       + context.PER_MESSAGE_OVERHEAD for item in conv)
        self.assertEqual(selection.estimated_input_tokens, expected)

    def test_selection_is_recorded_for_replay(self):
        conv = msgs(*[("user" if i % 2 == 0 else "assistant", 4000) for i in range(12)])
        _, sel = context.select(conv, window=8192, output_allowance=2048)
        d = sel.as_dict()
        for key in ("included_ids", "omitted_ids", "omitted_count", "context_window",
                    "output_allowance", "estimated_input_tokens",
                    "input_budget_tokens", "counting_method"):
            self.assertIn(key, d, f"{key} must persist so a reopened job shows "
                                  "the policy that ran then")

    def test_empty_conversation(self):
        payload, sel = context.select([], window=8192, output_allowance=2048)
        self.assertEqual(payload, [])
        self.assertEqual(sel.omitted_count, 0)

    def test_exact_boundary_keeps_the_budget(self):
        budget = context.input_budget(8192, 2048)
        chars = int((budget - context.PER_MESSAGE_OVERHEAD) * context.CHARS_PER_TOKEN) - 8
        payload, sel = context.select(msgs(("user", chars)),
                                      window=8192, output_allowance=2048)
        self.assertTrue(sel.newest_fits)
        self.assertLessEqual(sel.estimated_input_tokens, budget)
        self.assertEqual(len(payload), 1)

    def test_dense_script_selection_is_explicitly_an_estimate(self):
        """Selection is not enforcement; runtime overflow rejection is tested separately."""
        dense = [{"message_id": "d", "role": "user", "text": "中文" * 500}]
        _, sel = context.select(dense, window=8192, output_allowance=2048)
        self.assertIn('estimate', sel.counting_method)

    def test_isolation_between_conversations(self):
        a = msgs(("user", 100))
        b = msgs(("user", 100), ("assistant", 100))
        _, sa = context.select(a, window=8192, output_allowance=2048)
        _, sb = context.select(b, window=8192, output_allowance=2048)
        self.assertEqual(len(sa.included_ids), 1)
        self.assertEqual(len(sb.included_ids), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
