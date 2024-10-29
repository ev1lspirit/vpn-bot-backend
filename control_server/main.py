import subprocess
from functools import wraps
from flask import Flask, request, jsonify
import configparser
import os
import json
import typing as tp


app = Flask(__name__)
config_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "authconfig.ini")
cfgparser = configparser.ConfigParser()
cfgparser.read(config_path)

def vless_url():
    return "vless://{uuid}@{host}:{port}?security=reality&sni={SNI}&alpn={alpn}&fp=chrome&pbk={pbk}&sid={SID}&type=tcp&flow=xtls-rprx-vision&encryption=none#VLESS VPN (TG:@sweeetferrero)"


def parse_xray_server_credentials() -> dict:
    config = load_xray_configuration()
    reality_settings = config["inbounds"]["streamSettings"]["realitySettings"]
    output_json = {}
    output_json["SNI"] = reality_settings["dest"].split(":")[0]
    output_json["SID"] = reality_settings["shortIds"][0]
    output_json["pbk"] = cfgparser["Configuration"]["public_key"]
    output_json["port"] = config["inbounds"]["port"]
    output_json["alpn"] = "h2"
    return output_json


def load_xray_server_credentials() -> dict:
    json_fullpath = os.path.join(os.path.dirname(os.path.realpath(__file__)), "serverinfo.json")
    if not os.path.exists(json_fullpath):
        credentials = parse_xray_server_credentials()
        with open(json_fullpath, 'w') as file:
            json.dump(credentials, file, ident=4)
        return credentials

    with open(json_fullpath, 'r') as file:
        return json.load(file)


def validate_request(bot_token: str, ip_address: str) -> bool:
    return (bot_token == cfgparser["ControlCentre"]["bot_token"]
            and ip_address == cfgparser["ControlCentre"]["ip_address"])


def load_xray_configuration():
    with open(cfgparser["Configuration"]["path"], 'r') as json_file:
        return json.load(json_file)


def save_xray_configuration(dictionary: dict):
    with open(cfgparser["Configuration"]["path"], 'w') as file:
        json.dump(dictionary, file, indent=4)


def restart_xray():
    subprocess.run(["sudo", "systemctl", "restart", "xray"])


def authorized(func: tp.Callable):
    @wraps(func)
    def wrapped(*args, **kwargs):
        token = request.headers.get('Token')
        print(token, request.remote_addr)
        if not validate_request(token, request.remote_addr):
            return jsonify({"message": "Authorization failed"}), 403
        return func(*args, **kwargs)
    return wrapped


@app.route(rule="/add", methods=["POST"])
@authorized
def add_user_route_handler():
    uuid = request.json.get("uuid")
    if uuid is None:
        return jsonify({"message": "No uuid specified"}), 403
    config = load_xray_configuration()
    config['inbounds'][0]['settings']['clients'].append({"id": uuid, "email": f'{str(request.remote_addr)}@example.com'})
    save_xray_configuration(config)
    restart_xray()
    return jsonify({"message": "User added successfully"}), 200


@app.route(rule="/credentials", methods=["POST"])
@authorized
def make_qr_code_route_handler():
    uuid = request.json.get("uuid")
    if uuid is None:
        return jsonify({"message": "No uuid specified"}), 403
    credentials = load_xray_server_credentials()
    credentials["uuid"] = uuid
    credentials["host"] = cfgparser["Configuration"]["host"]
    return jsonify(vless_url().format(**credentials))


@app.route(rule="/delete", methods=["POST"])
@authorized
def delete_user_route_handler():
    uuid = request.json.get("uuid")
    if uuid is None:
        return jsonify({"message": "No uuid specified"}), 403
    config = load_xray_configuration()
    clients = config['inbounds'][0]['settings']['clients']
    config['inbounds'][0]['settings']['clients'] = [client for client in clients if client["uuid"] != uuid]
    save_xray_configuration(config)
    restart_xray()
    return jsonify({"message": "User added successfully"}), 200


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    app.run("127.0.0.1", 9000)
