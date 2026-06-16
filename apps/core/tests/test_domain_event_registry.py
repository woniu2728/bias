from apps.core.tests.common import *

class DomainEventRegistryTests(TestCase):
    def test_runtime_reset_clears_extension_event_listeners_and_restores_runtime_listeners(self):
        from apps.core.extensions.bootstrap import get_extension_host

        class TemporaryExtensionEvent:
            pass

        bus = get_forum_event_bus()
        bus.clear()

        def handle_temporary_event(event):
            return None

        bus.register(TemporaryExtensionEvent, handle_temporary_event)
        self.assertIn(TemporaryExtensionEvent, bus._listeners)

        reset_extension_runtime_state()

        self.assertNotIn(handle_temporary_event, bus._listeners.get(TemporaryExtensionEvent, []))
        get_extension_host()
        self.assertTrue(any(event_type is not TemporaryExtensionEvent for event_type in bus._listeners))

    def test_dispatches_handlers_for_extension_events(self):
        class DiscussionRefreshEvent:
            def __init__(self, discussion_id: int):
                self.discussion_id = discussion_id

        class RelatedRecordsRefreshEvent:
            def __init__(self, record_ids):
                self.record_ids = tuple(record_ids)

        bus = DomainEventBus()
        received = []

        def handle_discussion_refresh(event):
            received.append(("discussion", event.discussion_id))

        def handle_related_refresh(event):
            received.append(("related", event.record_ids))

        bus.register(DiscussionRefreshEvent, handle_discussion_refresh)
        bus.register(RelatedRecordsRefreshEvent, handle_related_refresh)
        bus.dispatch(DiscussionRefreshEvent(discussion_id=12))
        bus.dispatch(RelatedRecordsRefreshEvent(record_ids=(3, 7)))

        self.assertEqual(received, [("discussion", 12), ("related", (3, 7))])
