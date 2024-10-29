from functools import wraps
from aiogram.types import KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from abc import ABC, abstractmethod
from callbacks import *
from strings import YamlStrings
import logging

logging.basicConfig(level=logging.INFO)
strings = YamlStrings()
flag_aliases = {"FR": "🇫🇷", "ND": "🇳🇱", "FIN": "🇫🇮"}


def save_markup(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        if self._markup is not None:
            # logging.info(f'{self.__class__.__name__} markup exists')
            return self._markup
        # logging.info(f'{self.__class__.__name__} markup doesn\'t exist')
        self._markup = method(self, *args, **kwargs)
        return self._markup
    return wrapper


def months_endings_updater(value):
    if value % 10 == 1:
        return "Месяц"
    elif 2 <= value % 10 <= 4:
        return "Месяца"
    else:
        return "Месяцев"


class BaseKeyboard(ABC):
    __instance = None
    _builder = None
    _markup = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    def __init__(self, **kwargs):
        self.builder = self._builder()
        for kwkey, kwval in kwargs.items():
            setattr(self, kwkey, kwval)

    @staticmethod
    def pagination_pattern(*, offset: int, total: int, callback, offset_change=5):
        pages = total // offset_change if total % offset_change == 0 else total // offset_change + 1
        pages_count = InlineKeyboardButton(text=f"Страница {offset // offset_change + 1}/{pages}",
                                           callback_data="null")
        if total <= offset_change:
            return pages_count,
        if offset:
            print(total, offset, total // offset)

        next_action_button = None
        back_button = None
        forward_condition = not offset or (total // offset > 1 if total != 2 * offset else False)
        backward_condition = offset > 0

        if forward_condition:
            next_action_button = InlineKeyboardButton(text="👉 Следующая",
                                                      callback_data=callback(offset=offset + offset_change,
                                                                             total=total).pack())
        if backward_condition:
            back_button = InlineKeyboardButton(text="👈 Предыдущая",
                                               callback_data=callback(offset=offset - offset_change,
                                                                      total=total).pack())

        to_create = list(filter(lambda btn: btn is not None, [back_button, next_action_button]))
        if len(to_create) == 2:
            result = to_create[0], pages_count, to_create[1]
        else:
            result = pages_count, to_create[0]
        return result

    @abstractmethod
    @save_markup
    def markup(self):
        raise NotImplemented


class BaseReplyKeyboard(BaseKeyboard):
    _builder = ReplyKeyboardBuilder


class BaseInlineKeyboard(BaseKeyboard):
    _builder = InlineKeyboardBuilder


class SomeReplyKeyboard(BaseReplyKeyboard):

    def markup(self):
        connect_button = KeyboardButton(text="Создать подключение")
        help_button = KeyboardButton(text="Помощь")
        self.builder.add(connect_button, help_button)
        return self.builder.as_markup(resize_keyboard=True)




class StartInlineKeyboard(BaseInlineKeyboard):
    @save_markup
    def markup(self):
        connect_button = InlineKeyboardButton(text="🔐 Подключиться", callback_data=CreateConnectionCallback().pack())
        help_button = InlineKeyboardButton(text="❓ Помощь", callback_data=ShowHelpConnectionCallback().pack())
        my_servers = InlineKeyboardButton(text="📲 Мои подписки", callback_data=ShowSubscriptionsCallback().pack())
        xtls_docs = InlineKeyboardButton(text="📚 Подробнее о VLESS", url=strings["xtls_url"])
        self.builder.row(connect_button)
        self.builder.row(my_servers, help_button)
        self.builder.row(xtls_docs)
        return self.builder.as_markup()


def back_to_menu_button() -> InlineKeyboardButton:
    return InlineKeyboardButton(text='❌ В меню',
                                   callback_data=GoBackToMainMenuCallback().pack())


class BackToMainMenuKeyboard(BaseInlineKeyboard):

    def markup(self):
        self.builder.row(back_to_menu_button())
        return self.builder.as_markup()


class HelpInlineKeyboard(BaseInlineKeyboard):

    def __init__(self, neko_link, **kwargs):
        self.neko_link = neko_link
        super().__init__(**kwargs)

    @save_markup
    def markup(self):
        neko_link_button = InlineKeyboardButton(text="📱Клиент Nekobox", url=self.neko_link)
        go_back_button = InlineKeyboardButton(text="👈 Вернуться", callback_data=GoBackToMainMenuCallback().pack())
        instruction = InlineKeyboardButton(text="📖 Инструкция", url="https://google.com")
        self.builder.row(neko_link_button, instruction)
        self.builder.row(go_back_button)
        return self.builder.as_markup()


class SubscriptionsPaginationKeyboard(BaseInlineKeyboard):

    def __init__(self, *, button_text_iterator, offset, total, offset_change, **kwargs):
        self.button_text_iterator = button_text_iterator
        self.offset = offset
        self.total = total
        self.offset_change = offset_change
        super().__init__(**kwargs)

    def markup(self):
        for _, uuid, button_text in self.button_text_iterator:
            self.builder.row(InlineKeyboardButton(text=button_text, callback_data=SendSubscriptionCredentialsCallback(uuid=uuid).pack()))

        self.builder.row(*self.pagination_pattern(offset=self.offset, total=self.total, offset_change=self.offset_change,
                                             callback=NextSubscriptionPage))
        self.builder.row(back_to_menu_button())
        return self.builder.as_markup()


class ServerChoiceKeyboard(BaseInlineKeyboard):

    def __init__(self, servers, total: int, offset=0,  **kwargs):
        self.total = total
        self.offset = offset
        self.servers = servers
        super().__init__(**kwargs)

    def markup(self):
        for server in self.servers:
            button = InlineKeyboardButton(text=f'{flag_aliases[server.flag_code]} {server.location} | {server.alias}',
                                          callback_data=ChooseParticularServerCallback(
                                              server_id=server.id
                                          ).pack())
            self.builder.row(button)
        pagination = self.pagination_pattern(offset=self.offset, total=self.total, offset_change=2, callback=NextServerPageCallback)
        self.builder.row(*pagination)
        self.builder.row(back_to_menu_button())
        return self.builder.as_markup()


class SubscriptionDurationKeyboard(BaseInlineKeyboard):

    def __init__(self, server_data, tariffs, **kwargs):
        self.server_data = server_data
        self.tariffs = tariffs
        super().__init__(**kwargs)

    def markup(self):
        for tariff in self.tariffs:
            self.builder.row(
                InlineKeyboardButton(text=f"{tariff.duration} {months_endings_updater(tariff.duration).lower()}| {tariff.price} руб.",
                                     callback_data=ChooseServerTariffCallback(
                                         server_id=self.server_data.server_id,
                                         tariff_id=tariff.id
                                     ).pack())
            )
        undo_transition = InlineKeyboardButton(text='👈 Вернуться', callback_data=UndoTransitionToTariffs().pack())
        self.builder.row(back_to_menu_button(), undo_transition)
        return self.builder.as_markup()


class AcceptOrDeclineNewRequestKeyboard(BaseInlineKeyboard):

    def __init__(self, uid: str, server_ip: str, duration: int, **kwargs):
        self.uid = uid
        self.duration = duration
        self.server_ip = server_ip
        super().__init__(**kwargs)

    def markup(self):
        accept = InlineKeyboardButton(text="✅", callback_data=RequestAcceptedCallback(
            uid=self.uid,
            server_ip=self.server_ip,
            duration=self.duration
        ).pack())
        reject = InlineKeyboardButton(text="❌", callback_data=RequestRejectedCallback(
            uid=self.uid,
            server_ip=self.server_ip
        ).pack())
        self.builder.row(accept, reject)
        return self.builder.as_markup()






