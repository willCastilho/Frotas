# carro/models.py
from django.db import models
from django.utils import timezone
from datetime import timedelta

class Veiculo(models.Model):
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('manutencao', 'Manutenção'),
    ]
    
    modelo = models.CharField(max_length=100)
    marca = models.CharField(max_length=100)
    ano = models.IntegerField()
    cor = models.CharField(max_length=50)
    Data_compra = models.DateField()
    data_cadastro = models.DateTimeField(default=timezone.now)
    Show = models.BooleanField(default=True)
    picture = models.ImageField(upload_to="veiculos/", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ativo')
    
    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.ano})"
    
    def custo_mes_atual(self):
        hoje = timezone.now()
        primeiro_dia = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        custos = self.custos.filter(data__gte=primeiro_dia)
        return float(custos.aggregate(total=models.Sum('valor'))['total'] or 0)
    
    def custo_mes_anterior(self):
        hoje = timezone.now()
        primeiro_dia_mes_atual = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        ultimo_dia_mes_anterior = primeiro_dia_mes_atual - timedelta(days=1)
        primeiro_dia_mes_anterior = ultimo_dia_mes_anterior.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        custos = self.custos.filter(data__gte=primeiro_dia_mes_anterior, data__lt=primeiro_dia_mes_atual)
        return float(custos.aggregate(total=models.Sum('valor'))['total'] or 0)
    
    def comparacao_custos(self):
        atual = self.custo_mes_atual()
        anterior = self.custo_mes_anterior()
        
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
        
        return {
            'percentual': abs(round(diferenca)),
            'cor': cor,
            'direcao': direcao
        }


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