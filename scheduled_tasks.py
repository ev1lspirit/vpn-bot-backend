import logging
from aiogram import Bot
from containers import ServerSubscriber
from database import BaseConnectionState
from logic import XrayUpdateRequest, send_message_to_user
from strings import YamlStrings, YamlQueries

strings = YamlStrings()
queries = YamlQueries()
logger = logging.getLogger(__name__)


async def check_subscription_expiration_date(bot: Bot):
    logger.info("check_subscription_expiration_date has been triggered")
    with BaseConnectionState(db_name="xclient", password="roottoor") as conn:
        expired_subscribers = tuple(map(lambda cont: ServerSubscriber(*cont),
                                        await conn.select(queries["look_for_expired_subscriptions"])))
        for subscriber in expired_subscribers:
            vless_delete_request = XrayUpdateRequest(uuid=subscriber.uuid,
                                                     server_ip=subscriber.server_ip_address, user_id=subscriber.subscriber_id)
            delete_request_response = await vless_delete_request.make_request_to_server(method="delete")
            logger.error(delete_request_response)
            if delete_request_response is None:
                return
            await conn.execute(queries["delete_expired_user"], subscriber.uuid, autocommit=True)
            await send_message_to_user(bot, chat_id=subscriber.subscriber_id,
                                       text=strings["subscription_expired"].format(
                                           location=subscriber.server_location,
                                           alias=subscriber.server_alias,
                                           subscription_id=subscriber.uuid
                                        )
                                       )


async def delete_old_server_requests():
    logger.info("delete_old_server_requests has been triggered")
    with BaseConnectionState(db_name="xclient", password="roottoor") as conn:
        await conn.execute(queries["delete_old_server_requests"], autocommit=True)
