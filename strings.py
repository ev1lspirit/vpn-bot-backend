import os
import yaml


class BaseYaml:
    strings_path = None
    content = None

    def __new__(cls, *args, **kwargs) -> dict:
        if cls.content is None:
            with open(cls.strings_path, 'r', encoding='utf-8') as file:
                cls.content = yaml.safe_load(file)
        return cls.content


class YamlQueries(BaseYaml):
    strings_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "queries.yaml")


class YamlStrings(BaseYaml):
    strings_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "strings.yaml")
