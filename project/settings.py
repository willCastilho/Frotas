import os
from pathlib import Path

from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega variaveis de ambiente do arquivo .env (se existir)
load_dotenv(BASE_DIR / '.env')


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: mantenha a SECRET_KEY em segredo em producao!
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-troque-esta-chave-em-producao',
)

# SECURITY WARNING: nao rode com DEBUG ligado em producao!
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    if h.strip()
]

# Dominios confiaveis para CSRF (necessario com HTTPS, ex.: Railway).
# Ex.: DJANGO_CSRF_TRUSTED_ORIGINS=https://meuapp.up.railway.app
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',')
    if o.strip()
]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'auditlog',
    'contas',
    'carro',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
    'contas.middleware.AcessoMiddleware',
]

ROOT_URLCONF = 'project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'contas.context_processors.rbac',
            ],
        },
    },
]

WSGI_APPLICATION = 'project.wsgi.application'


# Autenticacao
# https://docs.djangoproject.com/en/5.2/topics/auth/default/

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'


# Logging
# https://docs.djangoproject.com/en/5.2/topics/logging/

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simples': {'format': '{levelname} {asctime} {name} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simples',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
#
# Em producao (ex.: Railway) basta definir a variavel DATABASE_URL que o
# provedor do PostgreSQL fornece. Localmente, se DATABASE_URL nao existir,
# usa as variaveis DB_* do arquivo .env (veja .env.example).

import dj_database_url  # noqa: E402

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600),
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'gestao_frotas'),
            'USER': os.environ.get('DB_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

STATICFILES_DIRS = [
    BASE_DIR / 'carro' / 'base' / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Armazenamento de arquivos.
# Em producao o disco do container e efemero (uploads somem a cada deploy), entao
# use um storage externo compativel com S3 (AWS S3, Cloudflare R2, MinIO...).
# Ative definindo USE_S3=True e as credenciais no ambiente.
USE_S3 = os.environ.get('USE_S3', 'False').lower() == 'true'

if USE_S3:
    _default_storage = {
        'BACKEND': 'storages.backends.s3.S3Storage',
        'OPTIONS': {
            'access_key': os.environ.get('AWS_ACCESS_KEY_ID'),
            'secret_key': os.environ.get('AWS_SECRET_ACCESS_KEY'),
            'bucket_name': os.environ.get('AWS_STORAGE_BUCKET_NAME'),
            'region_name': os.environ.get('AWS_S3_REGION_NAME', 'auto'),
            'endpoint_url': os.environ.get('AWS_S3_ENDPOINT_URL') or None,
            'querystring_auth': True,
            'file_overwrite': False,
        },
    }
else:
    _default_storage = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}

STORAGES = {
    'default': _default_storage,
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}


# E-mail (recuperacao de senha, convites, alertas).
# Sem SMTP configurado, os e-mails vao para o console (dev). Em producao,
# defina EMAIL_HOST/EMAIL_HOST_USER/EMAIL_HOST_PASSWORD no ambiente.
# Prioridade: API HTTP do Brevo (HTTPS/443, imune a bloqueio de SMTP) ->
# SMTP generico -> console (dev).
if os.environ.get('BREVO_API_KEY'):
    EMAIL_BACKEND = 'contas.email_backends.BrevoAPIBackend'
    BREVO_API_KEY = os.environ['BREVO_API_KEY']
elif os.environ.get('EMAIL_HOST'):
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST')
    EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    # SSL (porta 465) e TLS (porta 587) sao mutuamente exclusivos.
    EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() == 'true'
    EMAIL_USE_TLS = (not EMAIL_USE_SSL and
                     os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '465' if EMAIL_USE_SSL else '587'))
    EMAIL_TIMEOUT = int(os.environ.get('EMAIL_TIMEOUT', '10'))
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Gestão de Frotas <no-reply@frotas.app>')


# Monitoramento de erros (Sentry) - ativado se SENTRY_DSN estiver definido.
SENTRY_DSN = os.environ.get('SENTRY_DSN')
if SENTRY_DSN:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=float(os.environ.get('SENTRY_TRACES_RATE', '0.1')),
            send_default_pii=False,
        )
    except ImportError:
        pass


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
