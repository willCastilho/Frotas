# carro/models.py
from datetime import timedelta

from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone


def _inicio_mes(momento):
    return momento.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def comparacao_custos(atual, anterior):
    """Compara dois valores de custo e devolve percentual, cor e direcao.

    Regra de cor: caiu >=10% verde, variou +-10% amarelo, subiu >10% vermelho.
    """
    atual = float(atual or 0)
    anterior = float(anterior or 0)

    if anterior == 0:
        if atual == 0:
            return {'percentual': 0, 'cor': 'green', 'direcao': '—'}
        return {'percentual': 100, 'cor': 'red', 'direcao': '↑'}

    diferenca = ((atual - anterior) / anterior) * 100

    if diferenca <= -10:
        cor = 'green'
    elif -10 < diferenca <= 10:
        cor = 'yellow'
    else:
        cor = 'red'

    direcao = '↓' if diferenca < 0 else '↑' if diferenca > 0 else '—'

    return {'percentual': abs(round(diferenca)), 'cor': cor, 'direcao': direcao}


class VeiculoQuerySet(models.QuerySet):
    def com_custos_mensais(self):
        """Anota custo do mes atual e do anterior em uma unica query,
        evitando o N+1 ao listar veiculos."""
        agora = timezone.now()
        inicio_atual = _inicio_mes(agora)
        inicio_anterior = _inicio_mes(inicio_atual - timedelta(days=1))
        return self.annotate(
            custo_atual=Sum(
                'custos__valor',
                filter=Q(custos__data__gte=inicio_atual),
            ),
            custo_anterior=Sum(
                'custos__valor',
                filter=Q(
                    custos__data__gte=inicio_anterior,
                    custos__data__lt=inicio_atual,
                ),
            ),
        )


class Veiculo(models.Model):
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('manutencao', 'Manutenção'),
        ('vendido', 'Vendido'),
        ('baixado', 'Baixado'),
    ]

    modelo = models.CharField(max_length=100)
    marca = models.CharField(max_length=100)
    ano = models.IntegerField()
    cor = models.CharField(max_length=50)
    data_compra = models.DateField()
    data_cadastro = models.DateTimeField(default=timezone.now)
    picture = models.ImageField(upload_to="veiculos/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativo')

    objects = VeiculoQuerySet.as_manager()

    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.ano})"

    def custo_mes_atual(self):
        inicio = _inicio_mes(timezone.now())
        total = self.custos.filter(data__gte=inicio).aggregate(t=Sum('valor'))['t']
        return float(total or 0)

    def custo_mes_anterior(self):
        inicio_atual = _inicio_mes(timezone.now())
        inicio_anterior = _inicio_mes(inicio_atual - timedelta(days=1))
        total = self.custos.filter(
            data__gte=inicio_anterior, data__lt=inicio_atual
        ).aggregate(t=Sum('valor'))['t']
        return float(total or 0)

    def comparacao_custos(self):
        return comparacao_custos(self.custo_mes_atual(), self.custo_mes_anterior())


class Custo(models.Model):
    TIPO_CHOICES = [
        ('combustivel', '⛽ Combustível'),
        ('manutencao', '⚙️ Manutenção'),
        ('seguro', '🛡️ Seguro'),
        ('ipva', '💰 IPVA'),
        ('lavagem', '💧 Lavagem'),
        ('estacionamento', '🅿️ Estacionamento'),
        ('multa', '🚨 Multa'),
        ('outro', '📌 Outro'),
    ]

    veiculo = models.ForeignKey(Veiculo, on_delete=models.CASCADE, related_name='custos')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.TextField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateField(default=timezone.now)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data']

    def __str__(self):
        return f"{self.veiculo} - {self.tipo} - R$ {self.valor}"
