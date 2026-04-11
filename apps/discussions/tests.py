import json

from django.test import TestCase, Client
from ninja_jwt.tokens import RefreshToken

from apps.discussions.services import DiscussionService
from apps.posts.services import PostService
from apps.users.models import User


class DiscussionApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = User.objects.create_user(
            username="author",
            email="author@example.com",
            password="password123",
        )
        self.reader = User.objects.create_user(
            username="reader",
            email="reader@example.com",
            password="password123",
        )

    def auth_header(self, user):
        token = RefreshToken.for_user(user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_create_discussion_accepts_bearer_token(self):
        response = self.client.post(
            "/api/discussions/",
            data=json.dumps({
                "title": "JWT backed discussion",
                "content": "Created through the API.",
                "tag_ids": [],
            }),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["title"], "JWT backed discussion")
        self.assertEqual(payload["user"]["id"], self.author.id)

    def test_discussion_list_exposes_unread_state_and_mark_all_read(self):
        discussion = DiscussionService.create_discussion(
            title="Unread tracking",
            content="Initial post",
            user=self.author,
        )
        DiscussionService.get_discussion_by_id(discussion.id, self.reader)
        PostService.create_post(
            discussion_id=discussion.id,
            content="A new reply",
            user=self.author,
        )

        response = self.client.get(
            "/api/discussions/",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        discussion_payload = response.json()["data"][0]
        self.assertTrue(discussion_payload["is_unread"])
        self.assertEqual(discussion_payload["unread_count"], 1)

        response = self.client.post(
            "/api/discussions/read-all",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.get(
            "/api/discussions/",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        discussion_payload = response.json()["data"][0]
        self.assertFalse(discussion_payload["is_unread"])
        self.assertEqual(discussion_payload["unread_count"], 0)
