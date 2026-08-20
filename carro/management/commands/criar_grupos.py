from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from carro.models import (
    Abastecimento,
    Custo,
    PlanoManutencao,
    RegistroQuilometragem,
    Veiculo,
)

MODELOS = [Veiculo, Custo, Abastecimento, RegistroQuilometragem, PlanoManutencao]


def _perms(modelos, acoes):
    """Retorna as permissions (add/change/delete/view) dos modelos informados."""
    perms = []
    for modelo in modelos:
        ct = ContentType.objects.get_for_model(modelo)
        for acao in acoes:
            codename = f'{acao}_{modelo._meta.model_name}'
            try:
                perms.append(Permission.objects.get(content_type=ct, codename=codename))
            except Permission.DoesNotExist:
                pass
    return perms


class Command(BaseCommand):
    help = 'Cria os grupos de acesso (Administrador, Gestor, Operador, Consulta).'

    def handle(self, *args, **options):
        definicoes = {
            'Administrador': _perms(MODELOS, ['add', 'change', 'delete', 'view']),
            'Gestor': _perms(MODELOS, ['add', 'change', 'view']),
            'Operador': _perms(
                [Custo, Abastecimento, RegistroQuilometragem], ['add', 'view']
            ) + _perms([Veiculo, PlanoManutencao], ['view']),
            'Consulta': _perms(MODELOS, ['view']),
        }

        for nome, perms in definicoes.items():
            grupo, criado = Group.objects.get_or_create(name=nome)
            grupo.permissions.set(perms)
            estado = 'criado' if criado else 'atualizado'
            self.stdout.write(
                self.style.SUCCESS(f'Grupo "{nome}" {estado} ({len(perms)} permissões).')
            )
