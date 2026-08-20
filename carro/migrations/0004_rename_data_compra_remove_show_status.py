from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('carro', '0003_rename_show_veiculo_show_veiculo_status_custo'),
    ]

    operations = [
        migrations.RenameField(
            model_name='veiculo',
            old_name='Data_compra',
            new_name='data_compra',
        ),
        migrations.RemoveField(
            model_name='veiculo',
            name='Show',
        ),
        migrations.AlterField(
            model_name='veiculo',
            name='status',
            field=models.CharField(
                choices=[
                    ('ativo', 'Ativo'),
                    ('inativo', 'Inativo'),
                    ('manutencao', 'Manutenção'),
                    ('vendido', 'Vendido'),
                    ('baixado', 'Baixado'),
                ],
                default='ativo',
                max_length=20,
            ),
        ),
    ]
