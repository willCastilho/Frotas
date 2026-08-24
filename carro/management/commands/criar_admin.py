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
            self._garantir_admin_global(User.objects.get(username=username))
            return

        user = User.objects.create_superuser(
            username=username, email=email, password=password)
        self._garantir_admin_global(user)
        self.stdout.write(
            self.style.SUCCESS(f'Superusuario "{username}" criado.'))

    def _garantir_admin_global(self, user):
        """Garante que o superusuario seja o administrador GLOBAL do sistema
        (perfil admin, sem organizacao)."""
        from contas.models import PerfilUsuario

        perfil, _ = PerfilUsuario.objects.get_or_create(
            user=user,
            defaults={'papel': PerfilUsuario.PAPEL_ADMIN, 'organizacao': None})
        # Promove a admin global caso ja exista com outro papel/organizacao.
        if perfil.papel != PerfilUsuario.PAPEL_ADMIN or perfil.organizacao_id:
            perfil.papel = PerfilUsuario.PAPEL_ADMIN
            perfil.organizacao = None
            perfil.save(update_fields=['papel', 'organizacao'])
        self.stdout.write(self.style.SUCCESS('Admin global garantido.'))
