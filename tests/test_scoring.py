"""Combining-rule boundaries and invalid configuration checks."""

import unittest
from unittest.mock import patch

import config
import scoring


class ScoringTests(unittest.TestCase):
    def test_label_boundaries_have_no_gaps_or_overlap(self):
        for score, expected in [
            (0.0, 'human'), (0.3499, 'human'), (0.35, 'human'),
            (0.3501, 'unsure'), (0.5, 'unsure'), (0.6499, 'unsure'),
            (0.65, 'ai'), (0.6501, 'ai'), (1.0, 'ai'),
        ]:
            with self.subTest(score=score):
                guess, label = scoring.score_to_label(score)
                self.assertEqual(guess, expected)
                self.assertEqual(label, scoring.LABEL_TEXT[expected])
                self.assertNotIn('PLACEHOLDER', label)

    def test_invalid_combined_scores_and_cutoffs_are_rejected(self):
        for score in (-0.1, 1.1, float('nan'), float('inf')):
            with self.subTest(score=score), self.assertRaises(ValueError):
                scoring.score_to_label(score)
        with patch.object(config, 'HUMAN_THRESHOLD', 0.7), self.assertRaises(ValueError):
            scoring.score_to_label(0.5)

    def test_equal_weights_keep_disagreement_in_the_middle(self):
        self.assertEqual(scoring.combine_signals(0.9, 0.1), 0.5)
        self.assertEqual(scoring.combine_signals(0.1, 0.9), 0.5)
        self.assertEqual(scoring.combine_signals(0.0, 0.0), 0.0)
        self.assertEqual(scoring.combine_signals(1.0, 1.0), 1.0)

    def test_invalid_signals_are_rejected(self):
        for value in (-0.01, 1.01, float('nan'), float('inf')):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    scoring.combine_signals(value, 0.5)
                with self.assertRaises(ValueError):
                    scoring.combine_signals(0.5, value)

    def test_invalid_weights_cannot_create_a_misleading_score(self):
        for model_weight, style_weight in ((1.0, 1.0), (-0.5, 1.5), (float('nan'), 0.5)):
            with self.subTest(model_weight=model_weight, style_weight=style_weight):
                with patch.object(config, 'WEIGHT_MODEL_SIGNAL', model_weight), \
                     patch.object(config, 'WEIGHT_STYLE_SIGNAL', style_weight):
                    with self.assertRaises(ValueError):
                        scoring.combine_signals(0.7, 0.3)
