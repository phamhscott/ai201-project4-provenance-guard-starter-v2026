"""Checks for feature meaning, sparse input, and score direction."""

import math
import unittest

import stylometry


class StylometryTests(unittest.TestCase):
    def test_uniform_and_variable_sentence_lengths(self):
        uniform = "red blue. green gold."
        variable = "red. blue green gold."
        self.assertEqual(stylometry.sentence_length_spread(uniform), 0.0)
        self.assertEqual(stylometry.sentence_length_spread(variable), 0.5)
        self.assertLess(stylometry.style_signal(variable), stylometry.style_signal(uniform))

    def test_repetition_changes_the_score_without_changing_sentence_lengths(self):
        repeated = "red red. red red."
        varied = "red blue. green gold."
        self.assertEqual(stylometry.type_token_ratio(repeated), 0.25)
        self.assertEqual(stylometry.type_token_ratio(varied), 1.0)
        self.assertGreater(stylometry.style_signal(repeated), stylometry.style_signal(varied))

    def test_empty_and_single_sentence_inputs_remain_neutral(self):
        for text in ("", " ", "!!!", "One short sentence.", "!!! One sentence."):
            with self.subTest(text=text):
                self.assertEqual(stylometry.style_signal(text), 0.5)
        self.assertEqual(stylometry.type_token_ratio(""), 0.0)
        self.assertEqual(stylometry.punctuation_density(""), 0.0)

    def test_punctuation_and_apostrophe_handling(self):
        self.assertEqual(stylometry.words("It's it\u2019s"), ["it's", "it's"])
        self.assertEqual(stylometry.punctuation_density("Hi\u2014there!"), 2 / 9)
        self.assertEqual(stylometry.style_signal("red blue. green gold."),
                         stylometry.style_signal("red blue! green gold?"))

    def test_style_score_is_finite_and_bounded_for_extreme_spread(self):
        for text in ("one. " + "word " * 200 + ".", "one. two. three."):
            score = stylometry.style_signal(text)
            self.assertTrue(math.isfinite(score))
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 1.0)
