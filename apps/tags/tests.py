from django.test import TestCase
from ninja_jwt.tokens import RefreshToken

from apps.discussions.services import DiscussionService
from apps.tags.models import DiscussionTag, Tag
from apps.tags.services import TagService
from apps.users.models import User


class TagStatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tagger",
            email="tagger@example.com",
            password="password123",
        )
        self.tag = Tag.objects.create(
            name="生活",
            slug="life",
            color="#4d698e",
        )

    def test_create_discussion_refreshes_tag_count(self):
        DiscussionService.create_discussion(
            title="生活讨论 1",
            content="第一条生活内容",
            user=self.user,
            tag_ids=[self.tag.id],
        )
        DiscussionService.create_discussion(
            title="生活讨论 2",
            content="第二条生活内容",
            user=self.user,
            tag_ids=[self.tag.id],
        )

        self.tag.refresh_from_db()

        self.assertEqual(self.tag.discussion_count, 2)
        self.assertIsNotNone(self.tag.last_posted_discussion)

    def test_refresh_tag_stats_repairs_existing_discussion_count(self):
        discussion = DiscussionService.create_discussion(
            title="历史讨论",
            content="历史内容",
            user=self.user,
        )
        DiscussionTag.objects.create(discussion=discussion, tag=self.tag)
        Tag.objects.filter(id=self.tag.id).update(discussion_count=0)

        TagService.refresh_tag_stats([self.tag.id])
        self.tag.refresh_from_db()

        self.assertEqual(self.tag.discussion_count, 1)


class TagAccessApiTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="password123",
        )
        self.admin = User.objects.create_superuser(
            username="tag-admin",
            email="tag-admin@example.com",
            password="password123",
        )
        self.public_tag = Tag.objects.create(name="公开", slug="public-tag")
        self.members_tag = Tag.objects.create(
            name="成员区",
            slug="members-tag",
            view_scope=Tag.ACCESS_MEMBERS,
            start_discussion_scope=Tag.ACCESS_MEMBERS,
            reply_scope=Tag.ACCESS_MEMBERS,
        )
        self.staff_tag = Tag.objects.create(
            name="管理区",
            slug="staff-tag",
            view_scope=Tag.ACCESS_STAFF,
            start_discussion_scope=Tag.ACCESS_STAFF,
            reply_scope=Tag.ACCESS_STAFF,
        )

    def auth_header(self, user):
        token = RefreshToken.for_user(user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_guest_tag_list_hides_member_and_staff_tags(self):
        response = self.client.get("/api/tags")

        self.assertEqual(response.status_code, 200, response.content)
        slugs = [tag["slug"] for tag in response.json()["data"]]
        self.assertEqual(slugs, ["public-tag"])

    def test_member_tag_list_for_start_discussion_excludes_staff_only_tags(self):
        response = self.client.get(
            "/api/tags",
            {"purpose": "start_discussion"},
            **self.auth_header(self.member),
        )

        self.assertEqual(response.status_code, 200, response.content)
        slugs = {tag["slug"] for tag in response.json()["data"]}
        self.assertEqual(slugs, {"public-tag", "members-tag"})

    def test_guest_cannot_view_staff_tag_detail(self):
        response = self.client.get(f"/api/tags/{self.staff_tag.id}")

        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("没有权限", response.json()["error"])
