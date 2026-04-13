import json

from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from ninja_jwt.tokens import RefreshToken

from apps.discussions.services import DiscussionService
from apps.posts.services import PostService
from apps.tags.models import Tag
from apps.users.models import Group, Permission, User


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

    def test_discussion_detail_does_not_mark_everything_read_immediately(self):
        discussion = DiscussionService.create_discussion(
            title="Unread detail",
            content="Initial post",
            user=self.author,
        )
        DiscussionService.get_discussion_by_id(discussion.id, self.reader)
        PostService.create_post(
            discussion_id=discussion.id,
            content="Reply one",
            user=self.author,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content="Reply two",
            user=self.author,
        )

        response = self.client.get(
            f"/api/discussions/{discussion.id}",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["last_read_post_number"], 1)
        self.assertEqual(payload["unread_count"], 2)
        self.assertTrue(payload["is_unread"])

    def test_update_discussion_read_state_advances_progress(self):
        discussion = DiscussionService.create_discussion(
            title="Read state update",
            content="Initial post",
            user=self.author,
        )
        DiscussionService.get_discussion_by_id(discussion.id, self.reader)
        PostService.create_post(
            discussion_id=discussion.id,
            content="Reply one",
            user=self.author,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content="Reply two",
            user=self.author,
        )

        response = self.client.post(
            f"/api/discussions/{discussion.id}/read",
            data=json.dumps({
                "last_read_post_number": 2,
            }),
            content_type="application/json",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["last_read_post_number"], 2)

        response = self.client.get(
            f"/api/discussions/{discussion.id}",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["last_read_post_number"], 2)
        self.assertEqual(payload["unread_count"], 1)

    def test_discussion_list_filters_by_tag_slug(self):
        life_tag = Tag.objects.create(name="生活", slug="life", color="#4d698e")
        tech_tag = Tag.objects.create(name="技术", slug="tech", color="#3498db")

        life_discussion = DiscussionService.create_discussion(
            title="Life discussion",
            content="Only belongs to life.",
            user=self.author,
            tag_ids=[life_tag.id],
        )
        DiscussionService.create_discussion(
            title="Tech discussion",
            content="Only belongs to tech.",
            user=self.author,
            tag_ids=[tech_tag.id],
        )

        response = self.client.get("/api/discussions/", {"tag": life_tag.slug})

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["id"], life_discussion.id)
        self.assertEqual(payload["data"][0]["tags"][0]["slug"], life_tag.slug)

    def test_suspended_user_cannot_create_discussion(self):
        self.author.suspended_until = timezone.now() + timedelta(days=1)
        self.author.suspend_message = "封禁期间不可发帖"
        self.author.save(update_fields=["suspended_until", "suspend_message"])

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps({
                "title": "Should fail",
                "content": "Blocked content",
                "tag_ids": [],
            }),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("账号已被封禁", response.json()["error"])
        self.assertIn("封禁期间不可发帖", response.json()["error"])

    def test_discussion_can_enter_approval_queue(self):
        trusted_group = Group.objects.create(name="Trusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="startDiscussionWithoutApproval")

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps({
                "title": "Pending discussion",
                "content": "Needs approval",
                "tag_ids": [],
            }),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["approval_status"], "pending")
