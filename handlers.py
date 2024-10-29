import datetime
import logging
import uuid
import aiogram.exceptions
from aiogram.exceptions import TelegramAPIError
from containers import ServerContainer, TariffContainer, ServerRequest, ServerSubscriber
from aiogram import Router, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from keyboards import *
from database import BaseConnectionState
from logic import XrayUpdateRequest, make_qr_code, send_message_to_user
from strings import YamlStrings, YamlQueries
from dateutil.relativedelta import relativedelta
from config import botconf_parser

server_flags = {"France": "🇫🇷", "Netherlands": "🇳🇱", "Finland": "🇫🇮"}

logger = logging.getLogger(__name__)
router = Router(name=__name__)
strings = YamlStrings()
queries = YamlQueries()


@router.message(Command("start"), StateFilter(None))
async def start_command_handler(message: Message):
    reply_markup = StartInlineKeyboard().markup()
    logger.info(strings)
    await message.reply(text=strings["greetings"],
        reply_markup=reply_markup
    )


@router.callback_query(ShowSubscriptionsCallback.filter())
async def show_user_subscriptions_handler(callback: CallbackQuery):
    with BaseConnectionState(db_name="xclient") as conn:
        subscriptions_count = (await conn.select(queries["select_total_subscriptions"], callback.from_user.id))[0][0]
        subscriptions = map(lambda cont: ServerSubscriber(*cont),
            await conn.select(queries["select_active_subscriptions"], callback.from_user.id,
                              botconf_parser["BotParameters"]["subscriptions_page_size"],  0))

    user_subscriptions = tuple(map(lambda subscription: (strings["subscriptions_list"].format(
            uuid=subscription.uuid,
            valid_until=subscription.subscription_valid_until.strftime("%d.%m.%Y, %H:%M"),
            alias="".join(["<i>", subscription.server_alias, "</i>"]),
            country=subscription.server_location), subscription.uuid,
            f"{subscription.server_location}{server_flags[subscription.server_location]} | {subscription.server_alias}"),
                                   subscriptions))

    if not user_subscriptions:
        await callback.message.edit_text(text="Подписки не найдены", reply_markup=BackToMainMenuKeyboard().markup())
        return

    markup = SubscriptionsPaginationKeyboard(button_text_iterator=user_subscriptions,
                                             offset=0, offset_change=int(botconf_parser["BotParameters"]["subscriptions_page_size"]),
                                             total=subscriptions_count).markup()
    await callback.message.edit_text(text="".join(map(lambda x: f'{x[0]}\n\n', user_subscriptions)), reply_markup=markup)


@router.callback_query(NextSubscriptionPage.filter())
async def next_subscription_page_handler(callback: CallbackQuery, callback_data: CallbackData):
    offset, pages_count = callback_data.offset, callback_data.total
    with BaseConnectionState(db_name="xclient") as conn:
        subscriptions = map(lambda cont: ServerSubscriber(*cont),
                            await conn.select(queries["select_active_subscriptions"], callback.from_user.id,
                                              botconf_parser["BotParameters"]["subscriptions_page_size"], offset))

    user_subscriptions = tuple(map(lambda subscription: (strings["subscriptions_list"].format(
        uuid=subscription.uuid,
        valid_until=subscription.subscription_valid_until.strftime("%d.%m.%Y, %H:%M"),
        alias="".join(["<i>", subscription.server_alias, "</i>"]),
        country=subscription.server_location), subscription.uuid,
    f"{subscription.server_location}{server_flags[subscription.server_location]} | {subscription.server_alias}"), subscriptions))

    if not user_subscriptions:
        await callback.message.edit_text(text="Подписки не найдены", reply_markup=BackToMainMenuKeyboard().markup())
        return
    markup = SubscriptionsPaginationKeyboard(button_text_iterator=user_subscriptions,
                                             offset=offset, offset_change=int(
            botconf_parser["BotParameters"]["subscriptions_page_size"]),
                                             total=pages_count).markup()
    await callback.message.edit_text(text="".join(map(lambda x: f'{x[0]}\n\n', user_subscriptions)), reply_markup=markup)


@router.callback_query(ShowHelpConnectionCallback.filter())
async def help_command_handler(callback: CallbackQuery):
    await callback.message.edit_text(strings["help"], reply_markup=HelpInlineKeyboard(strings["nekobox_url"]).markup())


@router.callback_query(GoBackToMainMenuCallback.filter())
async def back_to_main_meny_handler(callback: CallbackQuery):
    await callback.message.edit_text(text=strings["greetings"], reply_markup=StartInlineKeyboard().markup())


@router.callback_query(UndoTransitionToTariffs.filter())
@router.callback_query(CreateConnectionCallback.filter())
async def create_connection_handler(callback: CallbackQuery, callback_data: CallbackData):
    with BaseConnectionState(db_name="xclient") as conn:
        if isinstance(callback_data, CreateConnectionCallback):
            requests_count = await conn.select(queries["select_total_requests_made_by_client"], callback.from_user.id)
            if requests_count[0][0] > 1:
                await callback.message.answer(
                    text=f"😔 Вы не можете отправлять более чем 2 запроса на покупку до одобрения администратором.",
                    reply_markup=BackToMainMenuKeyboard().markup())
                return
        servers_count = (await conn.select(queries["select_server_count"]))[0][0]
        logger.warning(int(botconf_parser["BotParameters"]["page_size"]))
        servers = map(lambda cont: ServerContainer(*cont),
                      await conn.select(queries["select_servers_with_offset"], int(botconf_parser["BotParameters"]["page_size"]), 0))

    markup = ServerChoiceKeyboard(servers, servers_count).markup()
    await callback.message.edit_text(strings["server_choice"], reply_markup=markup)


@router.callback_query(NextServerPageCallback.filter())
async def load_next_server_page(callback: CallbackQuery, callback_data: CallbackData):
    offset, servers_count = callback_data.offset, callback_data.total
    with BaseConnectionState(db_name="xclient") as conn:
        servers = map(lambda cont: ServerContainer(*cont),
                      await conn.select(queries["select_servers_with_offset"], int(botconf_parser["BotParameters"]["page_size"]), offset))
    markup = ServerChoiceKeyboard(servers, servers_count, offset=offset).markup()
    await callback.message.edit_reply_markup(reply_markup=markup)


@router.callback_query(ChooseParticularServerCallback.filter())
async def choose_server_handler(callback: CallbackQuery, callback_data: CallbackData):
    with (BaseConnectionState(db_name="xclient") as conn):
        already_made_request = await conn.select(queries["already_made_request"], callback.from_user.id, callback_data.server_id)
        if already_made_request:
            await callback.message.edit_text("Вы уже сделали запрос на этот сервер. Дождитесь ответа администрации.",
                                          reply_markup=BackToMainMenuKeyboard().markup())
            return
        already_have_subscription = await conn.select(
            queries["check_if_user_has_subscription"], callback.from_user.id, callback_data.server_id)
        if already_have_subscription:
            await callback.message.edit_text("📦 Вы уже приобрели подписку на данный сервер!",
                                          reply_markup=BackToMainMenuKeyboard().markup())
            return
        tariffs = map(lambda cont: TariffContainer(*cont), await conn.select(queries["select_tariffs"]))
    markup = SubscriptionDurationKeyboard(server_data=callback_data, tariffs=tariffs).markup()
    await callback.message.edit_text(text="💰 Выберите тарифный план: ", reply_markup=markup)


@router.callback_query(ChooseServerTariffCallback.filter())
async def choose_tariff_handler(callback: CallbackQuery, callback_data: CallbackData, bot: Bot):
    uid = uuid.uuid4()
    await callback.message.edit_text(
        text=strings["pay_for_subscription"].format(uid=uid,
                                                    today=datetime.datetime.today().strftime("%d.%m.%Y, %H:%M")),
                                     reply_markup=BackToMainMenuKeyboard().markup())
    with BaseConnectionState(db_name="xclient") as conn:
        server = next(map(lambda cont: ServerContainer(*cont),
                          await conn.select(queries["select_specific_server"], callback_data.server_id)))
        tariff = next(map(lambda cont: TariffContainer(*cont),
                          await conn.select(queries["select_specific_tariff"], callback_data.tariff_id)))
        await conn.execute(
            queries["insert_server_request"].format(
                uid=uid,
                user_id=callback.from_user.id,
                username="NULL" if callback.from_user.username is None else callback.from_user.username,
                server_id=callback_data.server_id,
                tariff_id=callback_data.tariff_id
                ), autocommit=True)

    await send_message_to_user(bot,
                            chat_id=int(botconf_parser["BotHost"]["id"]),
                            text=strings["accept_request_message"].format(
                               username=callback.from_user.username,
                               server_alias=server.alias,
                               server_location=server.location,
                               server_ip=server.ip_address,
                               tariff_duration=tariff.duration,
                               tariff_price=tariff.price
                           ), reply_markup=AcceptOrDeclineNewRequestKeyboard(str(uid), server.ip_address,
                                                                             tariff.duration).markup())


@router.callback_query(RequestAcceptedCallback.filter())
async def request_accepted_handler(callback: CallbackQuery, callback_data: CallbackData, bot: Bot):
    with BaseConnectionState(db_name="xclient") as conn:
        request = tuple(
            map(lambda cont:
                ServerRequest(*cont), await conn.select(queries["select_server_request"], callback_data.uid)))

        if not request:
            await bot.send_message(chat_id=botconf_parser["BotHost"]["id"],
                                   text="❌ Запрос не найден в базе данных. Возможно, он уже был удален планировщиком.")
            await callback.message.delete()
            return

        request = request[0]
        vless_update_request = XrayUpdateRequest(uuid=callback_data.uid,
                                                 server_ip=callback_data.server_ip, user_id=request.telegram_requester_id)
        add_request_result = await vless_update_request.make_request_to_server(method="add")
        credentials_request_result = await vless_update_request.make_request_to_server(method="credentials")
        if add_request_result is None or credentials_request_result is None:
            logger.error(f"Couldn't reach {callback_data.server_ip}. Check if the server is up")
            await callback.message.edit_text(text=f"Warning: Сервер недоступен в "
                                                  f"{datetime.datetime.now().strftime('%d.%m.%Y, %H:%M:%S')}!\n{callback.message.text}",
                                             reply_markup=callback.message.reply_markup)
            return

        vless_link = credentials_request_result["message"]
        image_bytes = make_qr_code(vless_link)
        await conn.execute(queries["delete_server_request"], callback_data.uid, autocommit=True)

        try:
            await bot.send_photo(chat_id=request.telegram_requester_id,
                                 photo=BufferedInputFile(file=image_bytes.getbuffer(),
                                                         filename="vless_link.png"),
                                 caption=strings["purchase_completed_message"])
        except TelegramAPIError as e:
            logger.error(f"Failed to send message to {request.telegram_requester_id}: {e}")
            await send_message_to_user(bot, chat_id=request.telegram_requester_id, text=strings["unexpected_error_message"])
            return

        await send_message_to_user(bot,
            chat_id=request.telegram_requester_id,
            text="📘 Полезные ссылки:",
            reply_markup=HelpInlineKeyboard(strings["nekobox_url"]).markup()
        )
        # await bot.send_message(chat_id=request.telegram_requester_id, text=vless_link)
        await callback.message.delete()
        await conn.execute(queries["insert_subscriber"], request.telegram_requester_id,
                           request.telegram_requester_username, autocommit=True)
        await conn.execute(queries["insert_subscription"],
                           request.requested_server, request.telegram_requester_id,
                           request.requested_tariff, callback_data.uid,
                           datetime.datetime.now() + relativedelta(months=+int(callback_data.duration)), autocommit=True)


@router.callback_query(RequestRejectedCallback.filter())
async def request_rejected_handler(callback: CallbackQuery, callback_data: CallbackData, bot: Bot):
    with BaseConnectionState(db_name="xclient") as conn:
        query_result = tuple(
            map(lambda cont:
                ServerRequest(*cont), await conn.execute(queries["delete_server_request"], callback_data.uid,
                                          autocommit=True, returning=True)))

        if not query_result:
            await bot.send_message(chat_id=botconf_parser["BotHost"]["id"],
                                   text="❌ Запрос не найден в базе данных. Возможно, он уже был удален планировщиком.")
            await callback.message.delete()
            return

        query_result = query_result[0]
        user_id = query_result.telegram_requester_id
    await send_message_to_user(
       bot,
       chat_id=user_id, text=strings["rejected_user_message"].format(uid=callback_data.uid)
    )
    await callback.message.delete()


@router.callback_query(SendSubscriptionCredentialsCallback.filter())
async def request_credentials_handler(callback: CallbackQuery, callback_data: CallbackData, bot: Bot):
    with BaseConnectionState(db_name="xclient", use_dict_cursor=True) as conn:
        subscription_details = await conn.select(queries["select_subscription_server"], callback.from_user.id,
                                                 callback_data.uuid)
    logger.error(f'{subscription_details} | {[callback.from_user.id, callback_data.uuid]}')
    server = ServerContainer(**subscription_details[0])
    credentials_request = XrayUpdateRequest(user_id=callback.from_user.id, server_ip=server.ip_address, uuid=callback_data.uuid)
    credentials_response = await credentials_request.make_request_to_server(method="credentials")
    if credentials_response is None:
        await bot.send_message(chat_id=callback.from_user.id, text=strings["unexpected_error_message"])
        logger.error(f"Couldn't reach {callback_data.server_ip}. Check if the server is up")
        return
    qr = make_qr_code(credentials_response["message"])
    try:
        await bot.send_photo(chat_id=callback.from_user.id, caption=strings["requested_qr_received"].format(
            server_alias=server.alias,
            server_location=server.location,
            flag=flag_aliases[server.flag_code]
        ), photo=BufferedInputFile(file=qr.getbuffer(), filename="vless_link.png"))
    except aiogram.exceptions.TelegramAPIError as e:
        logger.error(f"Failed to send message to {callback.from_user.id}: {e}")
        await send_message_to_user(bot, chat_id=callback.from_user.id, text=strings["unexpected_error_message"])
        return







