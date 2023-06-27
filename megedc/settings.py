import os
from datetime import timedelta
from megedc.utils import bool_from_str, get_env, passwd_file
from pathlib import Path
from tzlocal import get_localzone


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = passwd_file('DJANGO_SECRET_KEY_FILE',
                         'DJANGO_SECRET_KEY',
                         'PlsChgMe!')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = bool_from_str(get_env('DJANGO_DEBUG', 'true'))

ALLOWED_HOSTS = get_env('DJANGO_ALLOWED_HOSTS', '*').split(',')


# Application definition

INSTALLED_APPS = [
    'megedc.general',
    'megedc.x6gateapi',
    'megedc.data_export',
    'megedc.billing',
    'megedc.accuenergy',
    'megedc.apps.MegeDCAdminConfig',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rangefilter',
    'rest_framework.authtoken',
    'django_celery_beat',
    'django_celery_results',
    'django_json_widget',
    'tinymce',
    'django_jsonform',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'megedc.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'megedc' /'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'megedc.wsgi.application'


# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': get_env("DJANGO_DATABASES_DEFAULT_NAME", 'megedc'),
        'USER': get_env("DJANGO_DATABASES_DEFAULT_USER", 'megedc'),
        'PASSWORD': passwd_file('DJANGO_DATABASES_DEFAULT_PASSWORD_FILE',
                                'DJANGO_DATABASES_DEFAULT_PASSWORD',
                                'megedc'),
        'HOST': os.environ.get("DJANGO_DATABASES_DEFAULT_HOST", 'localhost'),
        'PORT': int(os.environ.get("DJANGO_DATABASES_DEFAULT_PORT", '5432')),
    }
}


# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = get_env('DJANGO_LANGUAGE_CODE', 'en-us')

TIME_ZONE = get_env('DJANGO_TIME_ZONE', str(get_localzone()))

USE_I18N = True

USE_L10N = True

USE_TZ = True

MEGEDC_URL = get_env('MEGEDC_URL', 'http://localhost').rstrip('/')

MEGEDC_URL_PATH = get_env('MEGEDC_URL_PATH', 'megedc').strip('/')

SESSION_COOKIE_PATH = '/' + MEGEDC_URL_PATH

CSRF_COOKIE_PATH = '/' + MEGEDC_URL_PATH

SESSION_COOKIE_SECURE = bool_from_str(
    get_env('DJANGO_SESSION_COOKIE_SECURE', 'f')
)

SECURE_SSL_REDIRECT = bool_from_str(
    get_env('DJANGO_SECURE_SSL_REDIRECT', 'f')
)

SECURE_SSL_HOST = get_env('DJANGO_SECURE_SSL_HOST', None)

SECURE_REDIRECT_EXEMPT = [
    r'^%s/version$' % (MEGEDC_URL_PATH),
    r'^%s/x6gateapi/.*$' % (MEGEDC_URL_PATH),
    r'^%s/data_export/.*$' % (MEGEDC_URL_PATH),
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/

STATIC_URL = get_env('DJANGO_STATIC_URL', MEGEDC_URL_PATH + '/static/')

MEDIA_ROOT = get_env('DJANGO_MEDIA_ROOT', 'media')

STATIC_ROOT = get_env('DJANGO_STATIC_ROOT', None)

STATICFILES_DIRS = [
    BASE_DIR / 'megedc' / 'static',
]

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

USE_X_FORWARDED_PORT = True
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'megedc.authentication.TokenLowerAuthentication',
    ],
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

CELERY_BROKER_URL = passwd_file('CELERY_BROKER_URL_FILE',
                                'CELERY_BROKER_URL',
                                'redis://localhost:6379/0')
CELERY_RESULT_EXPIRES = timedelta(
    days=int(get_env('CELERY_RESULT_EXPIRES_DAYS', '90'))
)
CELERY_RESULT_BACKEND = 'django-db'
CELERY_IMPORTS = ['megedc.billing.tasks', 'megedc.x6gateapi.tasks']

JASPERSERVER_URL = get_env(
    'JASPERSERVER_URL', 'http://localhost:8080'
).strip('/')
JASPERSERVER_USER = get_env('JASPERSERVER_USER', 'jasperadmin')
JASPERSERVER_PASSWORD = passwd_file('JASPERSERVER_PASSWORD_FILE',
                                    'JASPERSERVER_PASSWORD',
                                    'jasperadmin')

MEGEDC_JASPER_INVOICE_REPORT_PATH = {
    'PLAZA_REAL': get_env(
        'MEGEDC_JASPER_INVOICE_REPORT_PLAZA_REAL_PATH',
        'invoice_v1/Invoice_v1'
    ).strip('/'),
    'BUSINESS_PARK': get_env(
        'MEGEDC_JASPER_INVOICE_REPORT_BUSINESS_PARK_PATH',
        'invoice_v1/Invoice_v1'
    ).strip('/'),
} 


CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": passwd_file('DJANGO_CACHES_DEFAULT_LOCATION_FILE',
                                'DJANGO_CACHES_DEFAULT_LOCATION',
                                'redis://localhost:6379/0'),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}

EMAIL_HOST = get_env('DJANGO_EMAIL_HOST', 'localhost')
EMAIL_HOST_PASSWORD = passwd_file('DJANGO_EMAIL_HOST_PASSWORD_FILE',
                                 'DJANGO_EMAIL_HOST_PASSWORD',
                                 '')
EMAIL_HOST_USER = get_env('DJANGO_EMAIL_HOST_USER', '')
EMAIL_PORT = int(get_env('DJANGO_EMAIL_PORT', '25'))
EMAIL_USE_TLS = bool_from_str(get_env('DJANGO_EMAIL_USE_TLS', 'f'))
EMAIL_USE_SSL = bool_from_str(get_env('DJANGO_EMAIL_USE_SSL', 'f'))
DEFAULT_FROM_EMAIL = get_env(
    'DJANGO_DEFAULT_FROM_EMAIL',
    'webmaster@localhost'
)

TINYMCE_DEFAULT_CONFIG = {
    "theme": "silver",
    "height": 500,
    "menubar": True,
    "plugins": "advlist,autolink,lists,link,image,charmap,print,preview,anchor,"
    "searchreplace,visualblocks,code,fullscreen,insertdatetime,media,table,paste,"
    "code,help,wordcount",
    "toolbar": "undo redo | formatselect | "
    "bold italic backcolor | alignleft aligncenter "
    "alignright alignjustify | bullist numlist outdent indent | "
    "removeformat | help",
}

DATA_UPLOAD_MAX_NUMBER_FIELDS = int(
    get_env('DJANGO_DATA_UPLOAD_MAX_NUMBER_FIELDS', '1000')
)
