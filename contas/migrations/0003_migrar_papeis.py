from django.db import migrations


def migrar_papeis(apps, schema_editor):
    """Novo significado dos papeis:
    - 'admin' passa a ser o administrador GLOBAL do sistema. Os antigos 'admin'
      eram administradores de organizacao -> viram 'gestor'.
    - 'consulta' foi removido -> vira 'operador'.
    """
    PerfilUsuario = apps.get_model('contas', 'PerfilUsuario')
    PerfilUsuario.objects.filter(papel='admin').update(papel='gestor')
    PerfilUsuario.objects.filter(papel='consulta').update(papel='operador')


def reverter(apps, schema_editor):
    # Sem volta segura (nao ha como distinguir os antigos admins). No-op.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('contas', '0002_alter_perfilusuario_organizacao_and_more'),
    ]

    operations = [
        migrations.RunPython(migrar_papeis, reverter),
    ]
