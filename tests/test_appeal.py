"""Appeal state transitions against real temporary audit files."""

from pathlib import Path
import tempfile
import unittest

from unittest.mock import patch

import app
import audit
import config


class AppealTests(unittest.TestCase):
    def setUp(self):
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(config, "LOG_DIR", directory))
        self.enterContext(patch.object(config, "AUDIT_LOG", directory / "audit.jsonl"))
        self.client = app.app.test_client()
        self.original = audit.log_decision(
            content_id="existing-submission", creator_id="original_writer",
            guess="ai", model_score=0.9, style_score=0.8, combined_score=0.85,
            label="Original assessment.", stage="labeled",
        )

    def test_appeal_appends_status_without_overwriting_the_decision(self):
        body = {"content_id": "existing-submission", "reasoning": "Please review this decision."}
        # Extra creator data must not replace the original submission's creator.
        response = self.client.post("/appeal", json={**body, "creator_id": "different_writer"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["content_id"], body["content_id"])
        self.assertEqual(response.get_json()["status"], "under_review")
        entries = self.client.get("/log").get_json()["entries"]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0], self.original)
        self.assertEqual(entries[1]["status"], "under_review")
        self.assertEqual(entries[1]["event"], "appeal")
        self.assertEqual(entries[1]["content_id"], body["content_id"])
        self.assertEqual(entries[1]["creator_id"], "original_writer")
        self.assertEqual(entries[1]["reasoning"], body["reasoning"])

    def test_repeated_appeals_keep_the_original_and_record_both_explanations(self):
        for reason in ("First explanation.", "An additional detail."):
            response = self.client.post("/appeal", json={
                "content_id": "existing-submission", "reasoning": reason,
            })
            self.assertEqual(response.status_code, 200)
        entries = audit.entries_for("existing-submission")
        self.assertEqual(entries[0], self.original)
        self.assertEqual([entry["reasoning"] for entry in entries[1:]],
                         ["First explanation.", "An additional detail."])
        self.assertEqual(entries[-1]["status"], "under_review")

    def test_unknown_id_and_orphan_appeal_cannot_create_a_decision(self):
        audit.log_appeal("orphan", "test_writer", "No original decision exists.")
        before = audit.read_entries()
        for content_id in ("unknown", "orphan"):
            response = self.client.post("/appeal", json={
                "content_id": content_id, "reasoning": "Please review.",
            })
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.get_json()["error"], "content_not_found")
        self.assertEqual(audit.read_entries(), before)

    def test_bad_input_does_not_change_status_or_append_an_appeal(self):
        for payload in ([], {}, {"content_id": 42, "reasoning": "Review."},
                        {"content_id": "existing-submission", "reasoning": " "},
                        {"content_id": "existing-submission", "reasoning": None}):
            with self.subTest(payload=payload):
                response = self.client.post("/appeal", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"], "invalid_request")
        response = self.client.post("/appeal", data="{", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(audit.read_entries(), [self.original])
