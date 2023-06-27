import os
from django.conf import settings
from django.urls import reverse


def get_env(name, default=None):
    """
    Quick access to os.environ.get
    """
    return os.environ.get(name, default)


def passwd_file(file_env_name, env_name, default='PlsChgMe!'):
    """
    Get content of file path if exists or environment value or default value

    :param file_env_name: Environment var name with path of password file
    :param pass_env_name: Environment var name with password
    :default pass_env_name: Default value

    :returns: String conten of file or env or default
    """
    file_name = get_env(file_env_name, None)
    if file_name:
        if os.path.exists(file_name) and os.access(file_name, os.R_OK):
            with open(file_name, 'r') as file_open:
                return file_open.read()
    return get_env(env_name, default)


def bool_from_str(data):
    """
    Make  bool from string
    """
    if data is not None:
        dd = data.lower()
        if dd in ['false', 'f', 'n']:
            return False
        if dd in ['true', 't', 'y']:
            return True
    return None


def full_reverse(*args, **kwargs):
    return settings.MEGEDC_URL + reverse(*args, **kwargs)
