import grpc
from .partner_api_pb2 import (
    AuthenticationRequest,
    DeviceInventoryRequest,
    DeviceUsageRequest,
    ResultStatus,
    UsageChannel,
)
from .partner_api_pb2_grpc import PartnerApiStub
from django.core.cache import cache


class PartnerApiException(Exception):
    pass


class PartnerApiResponseException(PartnerApiException):

    def __init__(self, response, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.response = response

    @property
    def is_auth_invalid_credentials(self):
        status = self.response.result_status
        return status == ResultStatus.AUTH_INVALID_CREDENTIALS


class _PartnerApi():

    @classmethod
    def factory(cls, auth, host='partner.emporiaenergy.com', port=50051):
        return cls(auth, '%s:%s' % (host, port))

    def __init__(self, auth, target):
        self._auth = auth
        user, _ = self._auth
        self._auth_token_cache_key = 'partnerapi_authtoken_%s' % (user)
        self._stub = PartnerApiStub(grpc.insecure_channel(target))

    @property
    def stub(self):
        return self._stub

    @property
    def auth_token(self):
        token = cache.get(self._auth_token_cache_key, None)
        if token is None:
            partner_email, password = self._auth
            token = self.authenticate()
            if token:
                cache.set(self._auth_token_cache_key, token, timeout=3600)
            else:
                raise PartnerApiException("Invalid credentials")
        return token

    def _auth_token_renew(self):
        cache.delete(self._auth_token_cache_key)

    def authenticate(self):
        partner_email, password = self._auth
        request = AuthenticationRequest(
            partner_email=partner_email,
            password=password
        )
        try:
            response = self._stub.Authenticate(request)
        except grpc.RpcError as exce:
            if exce.code() == grpc.StatusCode.UNAUTHENTICATED:
                return False
            raise PartnerApiException() from exce

        if response.result_status == ResultStatus.VALID:
            return response.auth_token
        else:
            raise PartnerApiResponseException(response)

    def get_devices(self, customer_emails=None):
        request = DeviceInventoryRequest(
            auth_token=self.auth_token,
            customer_emails=customer_emails
        )
        response = self._stub.GetDevices(request)
        if response.result_status == ResultStatus.VALID:
            return response.devices
        elif response.result_status == ResultStatus.AUTH_EXPIRED:
            self._auth_token_renew()
            return self.get_devices(customer_emails)
        else:
            raise PartnerApiResponseException(response)

    def get_usage_data(self,
                       start,
                       end,
                       scale,
                       all_channels=False,
                       devices=None):
        request = DeviceUsageRequest(
            auth_token=self.auth_token,
            start_epoch_seconds=start,
            end_epoch_seconds=end,
            scale=scale,
            channels=UsageChannel.ALL if all_channels else UsageChannel.MAINS,
            manufacturer_device_id=devices
        )
        response = self._stub.GetUsageData(request)
        if response.result_status == ResultStatus.VALID:
            return response.device_usage
        elif response.result_status == ResultStatus.AUTH_EXPIRED:
            self._auth_token_renew()
            return self.get_usage_data(
                start,
                end,
                scale,
                all_channels=all_channels,
                devices=devices
            )
        else:
            raise PartnerApiResponseException(response)


partner_api = _PartnerApi.factory
