import requests


class AccuenergyApiClient():

    def __init__(self, base_url, token):
        self._base_url = base_url.rstrip('/')
        self._token = token

    @property
    def base_url(self):
        return self._base_url

    @property
    def token(self):
        return self._token

    def request(self, method, path, **kwargs):
        if 'params' not in kwargs:
            kwargs['params'] = {}
        if 'token' not in kwargs['params']:
            kwargs['params']['token'] = self.token
        url = self._base_url + path
        return requests.request(method, url, **kwargs)

    def get(self, path, **kwargs):
        return self.request('get', path, **kwargs)

    def get_readings_alarm(self):
        response = self.get('/api/readings/alarm')
        response.raise_for_status()
        return response.json()

    def get_settings_deviceInfo(self):
        response = self.get('/api/settings/deviceInfo')
        response.raise_for_status()
        return response.json()
