from django.db import migrations


def povoar(apps, schema_editor):
    """Cria uma organizacao padrao e vincula veiculos e usuarios existentes.
    Garante que nenhum dado fique sem organizacao apos a introducao do multi-tenant."""
    Plano = apps.get_model('contas', 'Plano')
    Organizacao = apps.get_model('contas', 'Organizacao')
    PerfilUsuario = apps.get_model('contas', 'PerfilUsuario')
    Veiculo = apps.get_model('carro', 'Veiculo')
    User = apps.get_model('auth', 'User')

    tem_dados = Veiculo.objects.exists() or User.objects.exists()
    if not tem_dados:
        return

    plano, _ = Plano.objects.get_or_create(
        slug='padrao',
        defaults={'nome': 'Padrão', 'preco_mensal': 0, 'limite_veiculos': 0},
    )
    org, _ = Organizacao.objects.get_or_create(
        nome='Organização Padrão',
        defaults={'plano': plano},
    )

    Veiculo.objects.filter(organizacao__isnull=True).update(organizacao=org)

    for user in User.objects.all():
        if not PerfilUsuario.objects.filter(user=user).exists():
            PerfilUsuario.objects.create(user=user, organizacao=org, papel='admin')


def reverter(apps, schema_editor):
    # Nao remove dados; apenas no-op para permitir rollback do schema.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('carro', '0008_veiculo_organizacao_and_more'),
        ('contas', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(povoar, reverter),
    ]
