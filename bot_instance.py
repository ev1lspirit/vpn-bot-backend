from argparse import ArgumentParser
from aiogram import Bot, Dispatcher


parser = ArgumentParser()
parser.add_argument("--token", help="Your bot token")
args = parser.parse_args()
bot = Bot(args.token, parse_mode="HTML")
dispatcher = Dispatcher()



