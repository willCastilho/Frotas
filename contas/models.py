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
    logo = models.ImageField(
        upload_to='logos/', null=True, blank=True,
        help_text='Logotipo exibido no topo do sistema (opcional).')
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
    """Papel do usuario no sistema (RBAC).

    - admin: administrador GLOBAL do sistema (manutencao/gestao da plataforma).
      Nao pertence a uma organizacao (organizacao = None). Ve apenas contagens
      agregadas e pode impersonar qualquer usuario para testes.
    - gestor: administrador da propria organizacao. Cria usuarios (ate gestor),
      cadastra veiculos/motoristas e gerencia os vinculos motorista x veiculo.
    - operador: motorista. So le os proprios dados e lanca abastecimento, km e
      custo apenas no seu unico veiculo vinculado.
    """
    PAPEL_ADMIN = 'admin'
    PAPEL_GESTOR = 'gestor'
    PAPEL_OPERADOR = 'operador'
    PAPEL_CHOICES = [
        (PAPEL_ADMIN, 'Administrador do sistema'),
        (PAPEL_GESTOR, 'Gestor da organização'),
        (PAPEL_OPERADOR, 'Operador (motorista)'),
    ]
    # Papeis que um gestor pode atribuir aos usuarios da propria organizacao.
    PAPEIS_DA_ORGANIZACAO = [
        (PAPEL_GESTOR, 'Gestor da organização'),
        (PAPEL_OPERADOR, 'Operador (motorista)'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil')
    organizacao = models.ForeignKey(
        Organizacao, on_delete=models.CASCADE, related_name='perfis',
        null=True, blank=True,
        help_text='Vazio para o administrador global do sistema.')
    papel = models.CharField(max_length=20, choices=PAPEL_CHOICES, default=PAPEL_GESTOR)

    def __str__(self):
        onde = self.organizacao or 'sistema'
        return f'{self.user} @ {onde} ({self.papel})'

    @property
    def eh_admin(self):
        """Administrador global do sistema."""
        return self.papel == self.PAPEL_ADMIN

    @property
    def eh_gestor(self):
        return self.papel == self.PAPEL_GESTOR

    @property
    def eh_operador(self):
        return self.papel == self.PAPEL_OPERADOR

    @property
    def pode_administrar(self):
        """Gerencia a organizacao (usuarios, veiculos, motoristas, vinculos)."""
        return self.eh_gestor

    @property
    def pode_escrever(self):
        """Escrita geral na organizacao (custos/veiculos/etc.). Operador tem
        escrita restrita ao proprio veiculo, tratada nas views."""
        return self.eh_gestor
