import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .guides import GUIDE_VERSION
from .models import GuidedTourProgress


class GuidedTourTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="guide-owner",
            password="test-password",
        )
        self.client.force_login(self.user)

    def post_progress(self, **overrides):
        payload = {
            "guide_key": "dashboard",
            "version": GUIDE_VERSION,
            "status": GuidedTourProgress.Status.COMPLETED,
        }
        payload.update(overrides)
        return self.client.post(
            reverse("guide_progress"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_guided_page_is_unseen_until_progress_is_saved(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["guided_tour"]["key"], "dashboard")
        self.assertFalse(response.context["guided_tour"]["has_seen"])
        self.assertContains(response, 'data-guide-key="dashboard"')

        self.post_progress()
        response = self.client.get(reverse("dashboard"))

        self.assertTrue(response.context["guided_tour"]["has_seen"])

    def test_progress_endpoint_creates_and_updates_one_record(self):
        response = self.post_progress()

        self.assertEqual(response.status_code, 200)
        progress = GuidedTourProgress.objects.get(user=self.user, guide_key="dashboard")
        self.assertEqual(progress.status, GuidedTourProgress.Status.COMPLETED)

        response = self.post_progress(status=GuidedTourProgress.Status.DISMISSED)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(GuidedTourProgress.objects.count(), 1)
        progress.refresh_from_db()
        self.assertEqual(progress.status, GuidedTourProgress.Status.DISMISSED)

    def test_progress_endpoint_rejects_unknown_guide_version_and_status(self):
        invalid_requests = [
            {"guide_key": "unknown"},
            {"version": GUIDE_VERSION + 1},
            {"status": "started"},
        ]

        for invalid_payload in invalid_requests:
            with self.subTest(invalid_payload=invalid_payload):
                response = self.post_progress(**invalid_payload)
                self.assertEqual(response.status_code, 400)

        self.assertFalse(GuidedTourProgress.objects.exists())

    def test_progress_endpoint_rejects_malformed_json(self):
        response = self.client.post(
            reverse("guide_progress"),
            data="not-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_progress_is_scoped_to_authenticated_user(self):
        self.post_progress()
        second_user = get_user_model().objects.create_user(
            username="guide-manager",
            password="test-password",
        )
        self.client.force_login(second_user)

        response = self.client.get(reverse("dashboard"))

        self.assertFalse(response.context["guided_tour"]["has_seen"])

    def test_anonymous_progress_request_redirects_to_login(self):
        client = Client()
        response = client.post(
            reverse("guide_progress"),
            data=json.dumps(
                {
                    "guide_key": "dashboard",
                    "version": GUIDE_VERSION,
                    "status": GuidedTourProgress.Status.COMPLETED,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
