from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(slots=True)
class ServerContainer:
    id: int = None
    alias: str = None
    ip_address: str= None
    location: str = None
    flag_code: str = None


@dataclass(slots=True)
class TariffContainer:
    id: int
    title: str
    price: int
    duration: int


@dataclass(slots=True)
class ServerRequest:
    uid: str
    telegram_requester_id: int
    telegram_requester_username: Optional[str] = None
    requested_server: int = None
    requested_tariff: int = None
    request_date: datetime = None


@dataclass(slots=True)
class ServerSubscriber:
    server_id: int
    subscriber_id: int
    tariff_id: int
    uuid: str
    subscription_valid_until: datetime
    server_alias: str
    server_ip_address: str
    server_location: str
    server_flag = None

