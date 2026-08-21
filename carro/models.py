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
    meta_custo_mensal = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Orcamento de custo por mes (opcional). Usado nos alertas.'
    )

    objects = VeiculoQuerySet.as_manager()

    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.ano})"

    def custo_vs_meta(self):
        """Compara o custo do mes atual com a meta. Retorna dict com pct (real),
        pct_barra (limitado a 100 para a largura) e cor."""
        meta = float(self.meta_custo_mensal or 0)
        if meta <= 0:
            return None
        atual = self.custo_mes_atual()
        pct = round(atual / meta * 100)
        if pct < 80:
            cor = 'green'
        elif pct <= 100:
            cor = 'yellow'
        else:
            cor = 'red'
        return {'meta': meta, 'pct': pct, 'pct_barra': min(pct, 100), 'cor': cor}

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

    def _leituras_km(self):
        """Todas as leituras de odometro conhecidas (abastecimentos + registros)."""
        km_abast = list(self.abastecimentos.values_list('quilometragem', flat=True))
        km_reg = list(self.registros_km.values_list('quilometragem', flat=True))
        return [k for k in km_abast + km_reg if k is not None]

    def km_atual(self):
        leituras = self._leituras_km()
        return max(leituras) if leituras else None

    def km_rodados(self):
        leituras = self._leituras_km()
        if len(leituras) < 2:
            return None
        return max(leituras) - min(leituras)

    def total_custos(self):
        total = self.custos.aggregate(t=Sum('valor'))['t']
        return float(total or 0)

    def custo_por_km(self):
        rodados = self.km_rodados()
        if not rodados:
            return None
        return self.total_custos() / rodados

    def consumo_medio(self):
        """Consumo medio em km/l pelo metodo de tanque cheio: distancia entre o
        primeiro e o ultimo abastecimento dividida pelos litros abastecidos
        depois do primeiro."""
        abast = list(self.abastecimentos.order_by('quilometragem'))
        if len(abast) < 2:
            return None
        km_total = abast[-1].quilometragem - abast[0].quilometragem
        litros_total = sum(float(a.litros) for a in abast[1:])
        if km_total <= 0 or litros_total <= 0:
            return None
        return km_total / litros_total


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

    # Tipos que o usuario pode lancar manualmente (combustivel entra so via
    # Abastecimento, para nao contar em dobro).
    TIPO_CHOICES_MANUAL = [c for c in TIPO_CHOICES if c[0] != 'combustivel']

    FORMA_PAGAMENTO_CHOICES = [
        ('dinheiro', 'Dinheiro'),
        ('pix', 'Pix'),
        ('debito', 'Cartão de débito'),
        ('credito', 'Cartão de crédito'),
        ('boleto', 'Boleto'),
        ('outro', 'Outro'),
    ]

    veiculo = models.ForeignKey(Veiculo, on_delete=models.CASCADE, related_name='custos')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.TextField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data = models.DateField(default=timezone.now)
    quilometragem = models.PositiveIntegerField(
        null=True, blank=True, help_text='Km do veiculo no momento do custo (opcional).'
    )
    fornecedor = models.CharField(max_length=120, blank=True)
    forma_pagamento = models.CharField(
        max_length=20, choices=FORMA_PAGAMENTO_CHOICES, blank=True
    )
    comprovante = models.FileField(
        upload_to='comprovantes/', null=True, blank=True,
        help_text='Foto/PDF da nota ou comprovante (opcional).'
    )
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data']

    def __str__(self):
        return f"{self.veiculo} - {self.tipo} - R$ {self.valor}"


class Abastecimento(models.Model):
    COMBUSTIVEL_CHOICES = [
        ('gasolina', 'Gasolina'),
        ('etanol', 'Etanol'),
        ('diesel', 'Diesel'),
        ('gnv', 'GNV'),
        ('flex', 'Flex'),
    ]

    veiculo = models.ForeignKey(
        Veiculo, on_delete=models.CASCADE, related_name='abastecimentos'
    )
    data = models.DateField(default=timezone.now)
    quilometragem = models.PositiveIntegerField()
    litros = models.DecimalField(max_digits=8, decimal_places=3)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    tipo_combustivel = models.CharField(
        max_length=20, choices=COMBUSTIVEL_CHOICES, default='gasolina'
    )
    posto = models.CharField(max_length=100, blank=True)
    # Custo de combustivel gerado automaticamente (fonte unica -> sem contagem dupla)
    custo = models.OneToOneField(
        Custo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='abastecimento'
    )
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-data', '-quilometragem']

    def __str__(self):
        return f"{self.veiculo} - {self.data} - {self.litros} L"

    @property
    def valor_litro(self):
        if self.litros:
            return float(self.valor_total) / float(self.litros)
        return 0.0

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Cria/atualiza o Custo de combustivel espelhado neste abastecimento.
        custo = self.custo or Custo()
        custo.veiculo = self.veiculo
        custo.tipo = 'combustivel'
        custo.valor = self.valor_total
        custo.data = self.data
        custo.quilometragem = self.quilometragem
        custo.fornecedor = self.posto
        custo.descricao = (
            f'Abastecimento de {self.litros} L'
            + (f' em {self.posto}' if self.posto else '')
        )
        custo.save()
        if self.custo_id != custo.id:
            self.custo = custo
            super().save(update_fields=['custo'])

    def delete(self, *args, **kwargs):
        custo = self.custo
        super().delete(*args, **kwargs)
        if custo:
            custo.delete()


class RegistroQuilometragem(models.Model):
    veiculo = models.ForeignKey(
        Veiculo, on_delete=models.CASCADE, related_name='registros_km'
    )
    data = models.DateField(default=timezone.now)
    quilometragem = models.PositiveIntegerField()
    origem = models.CharField(max_length=100, blank=True)
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ['-data', '-quilometragem']

    def __str__(self):
        return f"{self.veiculo} - {self.data} - {self.quilometragem} km"


class PlanoManutencao(models.Model):
    """Manutencao preventiva por km e/ou por prazo (ex.: troca de oleo,
    licenciamento). O status compara a proxima ocorrencia com o km atual do
    veiculo e com a data de hoje."""

    veiculo = models.ForeignKey(
        Veiculo, on_delete=models.CASCADE, related_name='planos_manutencao'
    )
    descricao = models.CharField(max_length=120)
    intervalo_km = models.PositiveIntegerField(
        null=True, blank=True, help_text='A cada quantos km (opcional)'
    )
    intervalo_dias = models.PositiveIntegerField(
        null=True, blank=True, help_text='A cada quantos dias (opcional)'
    )
    km_referencia = models.PositiveIntegerField(
        null=True, blank=True, help_text='Km da ultima realizacao'
    )
    data_referencia = models.DateField(
        null=True, blank=True, help_text='Data da ultima realizacao'
    )

    class Meta:
        ordering = ['descricao']

    def __str__(self):
        return f"{self.veiculo} - {self.descricao}"

    @property
    def proxima_km(self):
        if self.intervalo_km and self.km_referencia is not None:
            return self.km_referencia + self.intervalo_km
        return None

    @property
    def proxima_data(self):
        if self.intervalo_dias and self.data_referencia:
            return self.data_referencia + timedelta(days=self.intervalo_dias)
        return None

    def status(self, km_atual=None):
        """Retorna dict {cor, texto, detalhe}. Combina o alerta por km e por
        prazo, escolhendo o mais critico (vermelho > amarelo > verde)."""
        niveis = []
        detalhes = []

        if self.proxima_km is not None and km_atual is not None:
            faltam = self.proxima_km - km_atual
            margem = max(int((self.intervalo_km or 0) * 0.1), 500)
            if faltam <= 0:
                niveis.append('red')
                detalhes.append(f'Atrasada {abs(faltam)} km')
            elif faltam <= margem:
                niveis.append('yellow')
                detalhes.append(f'Faltam {faltam} km')
            else:
                niveis.append('green')
                detalhes.append(f'Faltam {faltam} km')

        if self.proxima_data is not None:
            faltam_dias = (self.proxima_data - timezone.now().date()).days
            if faltam_dias <= 0:
                niveis.append('red')
                detalhes.append(f'Vencida ha {abs(faltam_dias)} dias')
            elif faltam_dias <= 15:
                niveis.append('yellow')
                detalhes.append(f'Vence em {faltam_dias} dias')
            else:
                niveis.append('green')
                detalhes.append(f'Vence em {faltam_dias} dias')

        if 'red' in niveis:
            cor, texto = 'red', '🔴 Atrasada'
        elif 'yellow' in niveis:
            cor, texto = 'yellow', '🟡 Próxima'
        elif 'green' in niveis:
            cor, texto = 'green', '🟢 Em dia'
        else:
            cor, texto = 'gray', 'Sem parâmetros'

        return {'cor': cor, 'texto': texto, 'detalhe': ' · '.join(detalhes)}
