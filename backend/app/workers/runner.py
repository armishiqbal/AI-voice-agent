from __future__ import annotations

import asyncio
import logging
import signal

from app.core.config import settings
from app.repositories.bootstrap import create_schema_for_local_development
from app.repositories.conversation_state import ConversationStateStore
from app.repositories.transcripts import TranscriptStore
from app.services.follow_up_reminders import LeadFollowUpScheduler
from app.workers.handlers import build_internal_handlers, build_outbox_handlers
from app.workers.outbox import OutboxWorker

logger = logging.getLogger("awaaz.outbox")


async def run() -> None:
    if settings.app_env == "development":
        create_schema_for_local_development()
    handlers = {**build_internal_handlers(), **build_outbox_handlers(settings)}
    if not build_outbox_handlers(settings):
        logger.warning("No Google integration configured; outbox events will remain pending")
    worker = OutboxWorker(handlers, max_attempts=settings.outbox_max_attempts)
    follow_up_scheduler = LeadFollowUpScheduler()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass

    async def report_error(error: Exception) -> None:
        logger.error("Outbox poll failed: %s", error)

    async def retention_maintenance() -> None:
        while not stop.is_set():
            await asyncio.to_thread(TranscriptStore().purge_expired)
            await asyncio.to_thread(ConversationStateStore().purge_expired)
            try:
                await asyncio.wait_for(stop.wait(), timeout=3600)
            except TimeoutError:
                continue

    async def schedule_due_follow_ups() -> None:
        while not stop.is_set():
            try:
                queued = await asyncio.to_thread(follow_up_scheduler.enqueue_due)
                if queued:
                    logger.info("follow_up_reminders queued=%s", queued)
            except Exception as error:  # noqa: BLE001 - scheduler failures must not stop delivery
                logger.error("follow_up_reminders failed error_type=%s", type(error).__name__)
            try:
                await asyncio.wait_for(stop.wait(), timeout=60)
            except TimeoutError:
                continue

    await asyncio.gather(
        worker.run_forever(stop, poll_seconds=settings.outbox_poll_seconds, on_error=report_error),
        retention_maintenance(),
        schedule_due_follow_ups(),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Outbox worker stopped")


if __name__ == "__main__":
    main()
