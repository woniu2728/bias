from django.test import TestCase
from ninja_jwt.tokens import RefreshToken

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
            is_email_confirmed=True,
        )
        self.replier = User.objects.create_user(
            username="replier",
            email="replier@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.participant = User.objects.create_user(
            username="participant",
            email="participant@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.mentioned = User.objects.create_user(
            username="mentioned",
            email="mentioned@example.com",
            password="password123",
            is_email_confirmed=True,
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

    def test_multiple_replies_in_same_discussion_create_multiple_notifications(self):
        PostService.create_post(
            discussion_id=self.discussion.id,
            content="Second reply",
            user=self.replier,
        )
        PostService.create_post(
            discussion_id=self.discussion.id,
            content="Third reply",
            user=self.replier,
        )

        notifications = Notification.objects.filter(
            user=self.author,
            type="discussionReply",
            subject_id=self.discussion.id,
            is_read=False,
        ).order_by("id")

        self.assertEqual(notifications.count(), 3)
        self.assertEqual(
            [item.data["post_number"] for item in notifications],
            [2, 3, 4],
        )

    def auth_header(self, user):
        token = RefreshToken.for_user(user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_delete_all_read_endpoint_uses_clear_route(self):
        unread_before = Notification.objects.filter(user=self.author, is_read=False).count()
        Notification.objects.create(
            user=self.author,
            from_user=self.replier,
            type="postLiked",
            subject_type="post",
            subject_id=self.initial_reply.id,
            is_read=True,
            data={"post_id": self.initial_reply.id},
        )
        Notification.objects.create(
            user=self.author,
            from_user=self.participant,
            type="postReply",
            subject_type="post",
            subject_id=self.initial_reply.id,
            is_read=False,
            data={"post_id": self.initial_reply.id},
        )

        response = self.client.delete(
            "/api/notifications/read/clear",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Notification.objects.filter(user=self.author, is_read=True).count(), 0)
        self.assertEqual(Notification.objects.filter(user=self.author, is_read=False).count(), unread_before + 1)
