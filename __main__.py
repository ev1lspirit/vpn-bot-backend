import asyncio
from functools import partial
from bot_instance import bot, dispatcher
from handlers import router as handlers_router
from scheduled_tasks import check_subscription_expiration_date, delete_old_server_requests
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    dispatcher.include_router(handlers_router)
    scheduler = AsyncIOScheduler()
    subscription_checker = partial(check_subscription_expiration_date, bot=bot)
    scheduler.add_job(subscription_checker, 'cron', hour=0, minute=0)
    scheduler.add_job(delete_old_server_requests, CronTrigger(day_of_week='sun', hour=00, minute=00))
    scheduler.start()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(dispatcher.start_polling(bot))
    finally:
        scheduler.shutdown()
        loop.close()

if __name__ == "__main__":
    main()
