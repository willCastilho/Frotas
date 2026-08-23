from .veiculos import (
    home,
    detalhes_veiculo,
    novo_veiculo,
    editar_veiculo,
    excluir_veiculo,
)
from .custos import (
    novo_custo,
    editar_custo,
    deletar_custo,
)
from .frota import (
    novo_abastecimento,
    novo_registro_km,
    novo_plano_manutencao,
    novo_documento,
    excluir_abastecimento,
    excluir_registro_km,
    excluir_plano_manutencao,
    excluir_documento,
)
from .dashboard import dashboard
from .relatorios import relatorios, exportar_custos
from .motoristas import (
    motoristas,
    detalhes_motorista,
    novo_motorista,
    editar_motorista,
    excluir_motorista,
    nova_atribuicao,
    encerrar_atribuicao,
    excluir_atribuicao,
    relatorio_motoristas,
)

__all__ = [
    'home',
    'detalhes_veiculo',
    'novo_veiculo',
    'editar_veiculo',
    'excluir_veiculo',
    'novo_custo',
    'editar_custo',
    'deletar_custo',
    'novo_abastecimento',
    'novo_registro_km',
    'novo_plano_manutencao',
    'novo_documento',
    'excluir_abastecimento',
    'excluir_registro_km',
    'excluir_plano_manutencao',
    'excluir_documento',
    'dashboard',
    'relatorios',
    'exportar_custos',
    'motoristas',
    'detalhes_motorista',
    'novo_motorista',
    'editar_motorista',
    'excluir_motorista',
    'nova_atribuicao',
    'encerrar_atribuicao',
    'excluir_atribuicao',
    'relatorio_motoristas',
]
