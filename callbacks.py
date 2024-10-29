from aiogram.filters.callback_data import CallbackData


class CreateConnectionCallback(CallbackData, prefix="c-c"):
    pass


class ShowHelpConnectionCallback(CallbackData, prefix="s-hp"):
    pass


class GoBackToMainMenuCallback(CallbackData, prefix="g-bck"):
    pass


class ChooseParticularServerCallback(CallbackData, prefix="c-pa-s"):
    server_id: int


class ChooseServerTariffCallback(CallbackData, prefix="c-s-t-c"):
    server_id: int
    tariff_id: int


class UndoTransitionToTariffs(CallbackData, prefix="ut-tt"):
    pass


class NextServerPageCallback(CallbackData, prefix="ld-n"):
    offset: int
    total: int


class RequestAcceptedCallback(CallbackData, prefix="r-ac"):
    uid: str
    server_ip: str
    duration: int


class RequestRejectedCallback(CallbackData, prefix="r-rj"):
    uid: str
    server_ip: str


class ShowSubscriptionsCallback(CallbackData, prefix="s-ms"):
    pass


class NextSubscriptionPage(CallbackData, prefix="n-sp"):
    offset: int
    total: int


class SendSubscriptionCredentialsCallback(CallbackData, prefix="ss-cc"):
    uuid: str