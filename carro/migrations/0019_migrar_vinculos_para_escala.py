"""Migra os vinculos abertos (AtribuicaoVeiculo sem data_fim) para a nova
escala diaria, criando a escala de HOJE para cada motorista/veiculo com vinculo
em aberto. Assim os operadores continuam enxergando o seu veiculo no dia do
deploy; o gestor passa a montar a escala dos proximos dias."""
from django.db import migrations
from django.utils import timezone


def migrar(apps, schema_editor):
    AtribuicaoVeiculo = apps.get_model('carro', 'AtribuicaoVeiculo')
    EscalaDiaria = apps.get_model('carro', 'EscalaDiaria')
    hoje = timezone.now().date()

    veiculos_usados = set()
    motoristas_usados = set()
    for atrib in (AtribuicaoVeiculo.objects
                  .filter(data_fim__isnull=True)
                  .select_related('veiculo', 'motorista')
                  .order_by('-data_inicio', '-id')):
        # Respeita 1 veiculo/motorista por dia (o vinculo mais recente vence).
        if atrib.veiculo_id in veiculos_usados or atrib.motorista_id in motoristas_usados:
            continue
        if EscalaDiaria.objects.filter(
                data=hoje, veiculo_id=atrib.veiculo_id).exists():
            continue
        if EscalaDiaria.objects.filter(
                data=hoje, motorista_id=atrib.motorista_id).exists():
            continue
        EscalaDiaria.objects.create(
            organizacao_id=atrib.veiculo.organizacao_id,
            data=hoje,
            veiculo_id=atrib.veiculo_id,
            motorista_id=atrib.motorista_id,
            observacao='Migrado do vínculo anterior',
        )
        veiculos_usados.add(atrib.veiculo_id)
        motoristas_usados.add(atrib.motorista_id)


class Migration(migrations.Migration):

    dependencies = [
        ('carro', '0018_escaladiaria'),
    ]

    operations = [
        migrations.RunPython(migrar, migrations.RunPython.noop),
    ]
