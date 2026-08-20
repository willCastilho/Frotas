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
    excluir_abastecimento,
    excluir_registro_km,
    excluir_plano_manutencao,
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
    'excluir_abastecimento',
    'excluir_registro_km',
    'excluir_plano_manutencao',
]
