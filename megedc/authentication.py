from rest_framework.authentication import TokenAuthentication


class TokenLowerAuthentication(TokenAuthentication):

    keyword = 'token'
