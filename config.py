import configparser
import os

botconf_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "botconf.ini")
botconf_parser = configparser.ConfigParser()
botconf_parser.read(botconf_path)