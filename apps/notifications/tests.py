from django.test import TestCase

from apps.discussions.services import DiscussionService
from apps.notifications.models import Notification
from apps.posts.services import PostService
from apps.users.models import User


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author",
            email="author@example.com",
            password="password123",
        )
        self.replier = User.objects.create_user(
            username="replier",
            email="replier@example.com",
            password="password123",
        )
        self.participant = User.objects.create_user(
            username="participant",
            email="participant@example.com",
            password="password123",
        )
        self.mentioned = User.objects.create_user(
            username="mentioned",
            email="mentioned@example.com",
            password="password123",
        )

        self.discussion = DiscussionService.create_discussion(
            title="Notification discussion",
            content="Initial post",
            user=self.author,
        )
        self.initial_reply = PostService.create_post(
            discussion_id=self.discussion.id,
            content="First reply",
            user=self.participant,
        )

    def test_reply_to_post_creates_post_reply_notification(self):
        PostService.create_post(
            discussion_id=self.discussion.id,
            content="@author Thanks for the update",
            user=self.replier,
            reply_to_post_id=self.initial_reply.id,
        )

        notification = Notification.objects.filter(
            user=self.participant,
            type="postReply",
        ).latest("id")

        self.assertEqual(notification.data["discussion_id"], self.discussion.id)
        self.assertEqual(notification.data["reply_to_post_id"], self.initial_reply.id)
        self.assertEqual(notification.data["reply_to_post_number"], self.initial_reply.number)
        self.assertIn("post_number", notification.data)

    def test_like_notification_contains_post_number(self):
        PostService.like_post(self.initial_reply.id, self.replier)

        notification = Notification.objects.get(
            user=self.participant,
            type="postLiked",
            subject_id=self.initial_reply.id,
        )

        self.assertEqual(notification.data["discussion_id"], self.discussion.id)
        self.assertEqual(notification.data["post_id"], self.initial_reply.id)
        self.assertEqual(notification.data["post_number"], self.initial_reply.number)

    def test_mention_notification_contains_post_number(self):
        post = PostService.create_post(
            discussion_id=self.discussion.id,
            content=f"Hello @{self.mentioned.username}",
            user=self.replier,
        )

        notification = Notification.objects.get(
            user=self.mentioned,
            type="userMentioned",
            subject_id=post.id,
        )

        self.assertEqual(notification.data["discussion_id"], self.discussion.id)
        self.assertEqual(notification.data["post_id"], post.id)
        self.assertEqual(notification.data["post_number"], post.number)
