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
            self._garantir_organizacao(User.objects.get(username=username))
            return

        user = User.objects.create_superuser(
            username=username, email=email, password=password)
        self._garantir_organizacao(user)
        self.stdout.write(
            self.style.SUCCESS(f'Superusuario "{username}" criado.'))

    def _garantir_organizacao(self, user):
        """Garante que o superusuario tenha uma organizacao/perfil (admin)."""
        from contas.models import Organizacao, PerfilUsuario, Plano

        if PerfilUsuario.objects.filter(user=user).exists():
            return
        plano, _ = Plano.objects.get_or_create(
            slug='padrao',
            defaults={'nome': 'Padrão', 'preco_mensal': 0, 'limite_veiculos': 0})
        org, _ = Organizacao.objects.get_or_create(
            nome='Organização Padrão', defaults={'plano': plano})
        PerfilUsuario.objects.create(
            user=user, organizacao=org, papel=PerfilUsuario.PAPEL_ADMIN)
        self.stdout.write(self.style.SUCCESS('Organizacao/perfil garantidos.'))
