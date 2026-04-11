from django.test import TestCase

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
