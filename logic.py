import json
import urllib.request
import logging
from functools import wraps, partial
import ssl
import aiogram.exceptions
import qrcode
import io
from aiogram import Bot
from config import botconf_parser
from bot_instance import bot
from strings import YamlStrings


strings = YamlStrings()
logger = logging.getLogger(__name__)

def make_qr_code(vless_link):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(vless_link)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    return img_bytes


async def send_message_to_user(bot, chat_id: int, text: str, reply_markup=None):
    try:
        kwargs = {
            "chat_id": chat_id,
            "text": text
        }
        if reply_markup is not None:
            kwargs["reply_markup"] = reply_markup
        await bot.send_message(**kwargs)
    except aiogram.exceptions.TelegramAPIError as e:
        logger.error(f"Failed to send message to {chat_id}: {e}")


async def check_if_user_reachable(bot: Bot, chat_id: int):
    try:
        await bot.send_chat_action(chat_id=chat_id, action='typing')
    except aiogram.exceptions.TelegramAPIError as e:
        logger.info(f"{chat_id} is not reachable! Cause: {str(e)}")
        return False
    else:
        return True


def handle_network_errors(function):
    @wraps(function)
    async def wrapper(*args, **kwargs):
        try:
            return await function(*args, **kwargs)
        except urllib.error.URLError as e:
            return {"message": str(e), "status": None}
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return {"message": str(e), "status": None}
    return wrapper


def notify_admin(function=None, admin_id:int=None):
    if function is None:
        return partial(notify_admin, admin_id=admin_id)

    async def wrapper(self, method="credentials"):
        response_json = await function(self, method)
        if response_json.get("status", 200) != 200:
            await bot.send_message(chat_id=admin_id,
                                   text=f"The response code was not 200 from {self.server_ip}.\n"
                                        f"Message: {str(response_json['message']).replace('<', '').replace('>', '')}\n"
                                        f"Method: /{method}")
            logger.error(
                f"The response code was not 200 from {self.server_ip}.\n"
                f"Message: {str(response_json['message']).replace('<', '').replace('>', '')}\n"
                f"Method: /{method}"
            )
            return None
        return response_json
    return wrapper


class XrayUpdateRequest:
    url = "https://{server_ip}:4443/{method}"

    def __init__(self, uuid: str, server_ip: str, user_id: int):
        self.uuid = uuid
        self.server_ip = server_ip
        self.user_id = user_id
        self.token = bot.token
        self.headers = {
            "Content-Type": "application/json",
            "Token": bot.token,
            "UserId": user_id
        }
        self.data = json.dumps({
            "uuid": uuid
        }).encode('utf-8')
        self.context = ssl._create_unverified_context()

    @notify_admin(admin_id=botconf_parser["BotHost"]["id"])
    @handle_network_errors
    async def make_request_to_server(self, method="credentials") -> dict:
        assert isinstance(method, str)
        url = self.url.format(server_ip=self.server_ip, method=method)
        add_user_req = urllib.request.Request(url, data=self.data, headers=self.headers)
        logger.info(f"Making request to {url}")
        with urllib.request.urlopen(add_user_req, context=self.context) as response:
            status_code = response.getcode()
            if status_code != 200:
                logger.error(
                    f"Couldn't request the /{method}. Code: {status_code}")
                logger.error(json.loads(response.read().decode(response.info().get_param('charset') or 'utf-8')))
                return {"status": status_code, "message": response.read().decode(response.info().get_param('charset') or 'utf-8')}
            return json.loads(response.read().decode(response.info().get_param('charset') or 'utf-8'))



