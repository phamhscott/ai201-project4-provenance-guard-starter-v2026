"""Route/log integration checks with a mocked model, not detector evaluation."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

import app
import audit
import config
import detector
import stylometry


class SubmitTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        log_dir = Path(directory)
        self.enterContext(patch.object(config, "LOG_DIR", log_dir))
        self.enterContext(patch.object(config, "AUDIT_LOG", log_dir / "audit.jsonl"))
        self.signal = self.enterContext(patch.object(detector, "model_signal"))
        self.style = self.enterContext(patch.object(stylometry, "style_signal", return_value=0.23))
        self.client = app.app.test_client()

    def test_score_and_identifiers_survive_response_and_audit_log(self):
        self.signal.return_value = 0.73
        text = "  This is a paragraph. Keep its original whitespace.  "
        payload = {"text": text, "creator_id": "test_writer"}
        responses = [self.client.post("/submit", json=payload) for _ in range(2)]

        self.assertTrue(all(response.status_code == 200 for response in responses))
        bodies = [response.get_json() for response in responses]
        self.assertNotEqual(bodies[0]["content_id"], bodies[1]["content_id"])
        entries = audit.read_entries()
        self.assertEqual(len(entries), 2)
        self.assertEqual(self.signal.call_count, 2)
        self.signal.assert_called_with(text)
        self.style.assert_called_with(text)
        self.assertEqual(self.style.call_count, 2)
        for body, entry in zip(bodies, entries):
            self.assertEqual(str(uuid.UUID(body["content_id"])), body["content_id"])
            self.assertEqual(entry["content_id"], body["content_id"])
            self.assertEqual(entry["creator_id"], "test_writer")
            self.assertEqual(entry["model_score"], body["model_score"])
            self.assertEqual(body["model_score"], 0.73)
            self.assertEqual(body["confidence"], 0.48)
            self.assertEqual(body["style_score"], 0.23)
            self.assertEqual(entry["style_score"], body["style_score"])
            self.assertEqual(entry["combined_score"], body["confidence"])
            self.assertEqual(entry["stage"], "combined_signals")
            self.assertEqual(entry["status"], body["status"])
            self.assertEqual(entry["guess"], body["guess"])
            self.assertEqual(entry["label"], body["label"])
            self.assertIn("timestamp", entry)

    def test_invalid_requests_are_rejected_before_the_model_runs(self):
        cases = [
            ([], 400),
            ({"text": None, "creator_id": "test_writer"}, 400),
            ({"text": "Valid writing.", "creator_id": " "}, 400),
            ({"text": "x" * (config.MAX_TEXT_CHARACTERS + 1),
              "creator_id": "test_writer"}, 413),
        ]
        for payload, expected_status in cases:
            with self.subTest(expected_status=expected_status, kind=type(payload).__name__):
                response = self.client.post("/submit", json=payload)
                self.assertEqual(response.status_code, expected_status)
                self.assertNotIn("guess", response.get_json())
        malformed = self.client.post("/submit", data="{", content_type="application/json")
        self.assertEqual(malformed.status_code, 400)
        self.signal.assert_not_called()
        self.style.assert_not_called()
        entries = audit.read_entries()
        self.assertEqual(len(entries), len(cases) + 1)
        self.assertTrue(all(entry["status"] == "rejected" for entry in entries))

    def test_exact_character_limit_is_accepted(self):
        self.signal.return_value = 0.42
        text = "x" * config.MAX_TEXT_CHARACTERS
        response = self.client.post("/submit", json={"text": text, "creator_id": "test_writer"})
        self.assertEqual(response.status_code, 200)
        self.signal.assert_called_once_with(text)

    def test_detector_failures_never_become_successful_decisions(self):
        for failure, status, code in [
            (ValueError("Text is too short to score."), 422, "text_too_short"),
            (detector.DetectorUnavailable("No model."), 503, "detector_unavailable"),
        ]:
            with self.subTest(code=code):
                self.signal.side_effect = failure
                response = self.client.post(
                    "/submit", json={"text": "Some writing.", "creator_id": "test_writer"}
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.get_json()["error"], code)
                self.assertNotIn("model_score", response.get_json())
        self.assertTrue(all(entry["status"] == "rejected" for entry in audit.read_entries()))
        self.style.assert_not_called()


if __name__ == "__main__":
    unittest.main()
