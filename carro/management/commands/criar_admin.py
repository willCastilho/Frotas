import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('Cria um superusuario a partir das variaveis DJANGO_SUPERUSER_* '
            'se ainda nao existir. Idempotente: nao falha se ja existir.')

    def handle(self, *args, **options):
        User = get_user_model()
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')

        if not username or not password:
            self.stdout.write(
                'DJANGO_SUPERUSER_USERNAME/PASSWORD nao definidos; pulando.')
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.SUCCESS(f'Superusuario "{username}" ja existe.'))
            return

        User.objects.create_superuser(
            username=username, email=email, password=password)
        self.stdout.write(
            self.style.SUCCESS(f'Superusuario "{username}" criado.'))
