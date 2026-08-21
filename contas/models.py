from django.conf import settings
from django.db import models
from django.utils import timezone


class Plano(models.Model):
    """Plano de assinatura. limite_veiculos = 0 significa ilimitado."""
    nome = models.CharField(max_length=60)
    slug = models.SlugField(unique=True)
    preco_mensal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    limite_veiculos = models.PositiveIntegerField(
        default=0, help_text='0 = ilimitado')
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['preco_mensal']

    def __str__(self):
        return self.nome


class Organizacao(models.Model):
    """Conta/empresa cliente. Todos os dados sao isolados por organizacao."""
    nome = models.CharField(max_length=120)
    criado_em = models.DateTimeField(default=timezone.now)

    plano = models.ForeignKey(
        Plano, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='organizacoes')
    assinatura_ativa = models.BooleanField(default=True)
    assinatura_valida_ate = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['nome']

    def __str__(self):
        return self.nome

    @property
    def limite_veiculos(self):
        return self.plano.limite_veiculos if self.plano else 0

    def atingiu_limite_veiculos(self):
        limite = self.limite_veiculos
        if not limite:  # 0 = ilimitado
            return False
        return self.veiculos.count() >= limite

    def assinatura_em_dia(self):
        if not self.assinatura_ativa:
            return False
        if self.assinatura_valida_ate and self.assinatura_valida_ate < timezone.now().date():
            return False
        return True


class PerfilUsuario(models.Model):
    """Vincula um usuario a uma organizacao e define seu papel (RBAC por conta)."""
    PAPEL_ADMIN = 'admin'
    PAPEL_GESTOR = 'gestor'
    PAPEL_OPERADOR = 'operador'
    PAPEL_CONSULTA = 'consulta'
    PAPEL_CHOICES = [
        (PAPEL_ADMIN, 'Administrador'),
        (PAPEL_GESTOR, 'Gestor'),
        (PAPEL_OPERADOR, 'Operador'),
        (PAPEL_CONSULTA, 'Consulta'),
    ]
    # Papeis que podem criar/editar/excluir
    PAPEIS_ESCRITA = {PAPEL_ADMIN, PAPEL_GESTOR, PAPEL_OPERADOR}
    # Papeis que administram a organizacao (usuarios, plano)
    PAPEIS_ADMIN = {PAPEL_ADMIN}

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil')
    organizacao = models.ForeignKey(
        Organizacao, on_delete=models.CASCADE, related_name='perfis')
    papel = models.CharField(max_length=20, choices=PAPEL_CHOICES, default=PAPEL_ADMIN)

    def __str__(self):
        return f'{self.user} @ {self.organizacao} ({self.papel})'

    @property
    def pode_escrever(self):
        return self.papel in self.PAPEIS_ESCRITA

    @property
    def pode_administrar(self):
        return self.papel in self.PAPEIS_ADMIN
