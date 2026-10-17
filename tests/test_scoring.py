"""Combining-rule boundaries and invalid configuration checks."""

import unittest
from unittest.mock import patch

import config
import scoring


class ScoringTests(unittest.TestCase):
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
