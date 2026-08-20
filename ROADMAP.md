# 🗺️ Roadmap — Gestão de Frotas

Guia de evolução do projeto, do estado atual até um sistema completo de gestão
de frota. A ordem foi pensada para **corrigir o que quebra primeiro**, depois
construir uma **fundação de código sólida**, e só então investir na **modelagem
de domínio** (que é onde está o maior valor gerencial).

> Princípio geral: **YAGNI** — modelar bem, mas só construir a regra de negócio
> quando ela for realmente usada. Um item de domínio por vez, cada um com sua
> tela e seu teste. Evitar transformar o sistema num "Frankenstein" por excesso
> de escopo.

Legenda: ✅ concluído · 🔴 crítico · 🟠 alto · 🟡 médio · 🔵 baixo/opcional

---

## ✅ Fase 0 — Já concluído

Feito na criação do repositório:

- [x] Remoção do `venv/` do versionamento
- [x] `requirements.txt` com dependências fixadas
- [x] `SECRET_KEY`, `DEBUG` e `ALLOWED_HOSTS` via variáveis de ambiente (`.env`)
- [x] Banco em **MySQL** (saímos do SQLite) — configurado via `.env`
- [x] `.gitignore`, `.env.example` e script `scripts/create_database.sql`
- [x] `README.md` com instruções de instalação e uso

> Observação: a stack de banco já é adequada para produção (MySQL). **Não há
> necessidade de migrar para PostgreSQL** — seria esforço sem retorno.

---

## ✅ Fase 1 — Estabilizar (concluída)

Correções que impediam o uso. Cobertas por testes em `carro/tests.py`.

- [x] 🔴 **Bug da home com banco vazio** — o `context` estava indentado dentro
  do `for` em `carro/views/carro_views.py`; com a lista de veículos vazia
  ocorria `UnboundLocalError` (erro 500). O `context` foi movido para fora do
  loop. Regressão coberta por `HomeTests.test_home_com_banco_vazio`.
- [x] 🔴 **Exclusão via GET** — `excluir_veiculo` e `deletar_custo` agora usam
  `@require_POST`, e os templates enviam `<form method="post">` com
  `{% csrf_token %}` no lugar de links. Coberto por `ExclusaoTests`.
- [x] 🟠 **Autenticação básica** — todas as views têm `@login_required`; fluxo
  de login/logout via `django.contrib.auth.urls`, com `registration/login.html`
  e barra de topo com "Sair". Perfis granulares ficam para a Fase 5.

---

## ✅ Fase 2 — Fundação de código (concluída)

Base pronta para crescer sem virar bagunça.

- [x] 🟡 **Camada de Forms** — `carro/forms.py` com `VeiculoForm` e `CustoForm`
  (`ModelForm`), incluindo validação de ano (1900–2100) e valor (> 0). As views
  e os templates de formulário agora usam esses forms.
- [x] 🟡 **Organizar as views** — `carro_views.py` dividido em
  `views/veiculos.py` e `views/custos.py`, reexportados em `views/__init__.py`.
- [x] 🟠 **Resolver o N+1 de queries** — `VeiculoQuerySet.com_custos_mensais()`
  anota custo do mês atual e anterior via `Sum` + `filter`, calculando a lista
  em uma query em vez de várias por veículo.
- [x] 🟡 **Paginação** na listagem de veículos (`Paginator`, 9 por página).
- [x] 🟡 **Testes** — 11 testes cobrindo login, home, exclusão, validação de
  forms e fluxo de custo.
- [x] 🔵 **Limpeza de modelo** — `Data_compra` → `data_compra` e remoção do
  campo `Show` (migração `0004`). Status ganhou `vendido` e `baixado`.

---

## ✅ Fase 3 — Modelagem de domínio (concluída)

O sistema deixou de ser "CRUD de veículo" e virou gestão de frota.

- [x] **Abastecimento como entidade própria** (`Abastecimento`: data,
  quilometragem, litros, valor_total, tipo_combustivel, posto) com propriedade
  `valor_litro`. Habilita **consumo médio (km/l)** e **custo por km**.
- [x] **Histórico de quilometragem** (`RegistroQuilometragem`) — leituras de
  odômetro ao longo do tempo; `Veiculo.km_atual()` usa a maior leitura conhecida.
- [x] **Manutenção preventiva com alerta** (`PlanoManutencao`) — por km e/ou por
  data, com status 🟢 em dia · 🟡 próximo · 🔴 atrasado (`plano.status(km_atual)`).
- [x] **Situação do veículo mais rica** — `vendido` e `baixado` (feito na Fase 2).
- [x] **Indicadores na página do veículo** — km atual, consumo médio e custo/km,
  além das listas de abastecimentos, quilometragem e planos de manutenção.
- [x] **CRUD** — criação pelo front-end (formulário genérico) e exclusão via
  POST; todas as entidades também registradas no Django admin.
- [ ] 🔵 **Dados cadastrais adicionais** (placa única, Renavam, chassi) —
  adiar até serem realmente usados (YAGNI).

---

## ✅ Fase 4 — Camada gerencial (concluída)

- [x] **Dashboard** (`/dashboard/`) — KPIs (veículos, ativos, em manutenção,
  custo do mês), gráfico de barras dos custos dos últimos 6 meses (CSS puro,
  sem libs externas), ranking dos veículos por custo e **alertas de manutenção
  da frota** (planos vencidos/próximos).
- [x] **Relatórios** (`/relatorios/`) — custos por categoria e por veículo, com
  filtro de período.
- [x] **Exportação** — CSV (com BOM/`;` para Excel PT-BR) e Excel (`openpyxl`).
- [x] **Navegação** — barra de topo com Dashboard / Veículos / Relatórios.

> A busca/filtro na listagem de veículos (marca, status) já existia na home; a
> faixa de ano fica como melhoria opcional futura.

---

## 🏗️ Fase 5 — Profissionalização (se/quando for para produção real)

- [ ] **Perfis e permissões** (RBAC) — Admin / Gestor / Operador / Consulta,
  usando `Groups`/`Permissions` do Django. Só quando existir um segundo tipo de
  usuário real.
- [ ] **Auditoria** — quem alterou o quê e quando. Usar biblioteca pronta
  (`django-auditlog` ou `django-simple-history`) em vez de tabela própria.
- [ ] **Deploy** — Docker + Gunicorn + Nginx, `DEBUG=False`, HTTPS.
- [ ] **CI/CD** — rodar testes e lint a cada push (GitHub Actions).
- [ ] **Backups e logs** estruturados.

---

## Ordem recomendada (resumo)

1. **Fase 1** — corrigir os 2 bugs + login básico. *(horas)*
2. **Fase 2** — forms, organização de views, N+1, testes. *(dias)*
3. **Fase 3** — Abastecimento → Quilometragem → Manutenção preventiva. *(o coração do projeto)*
4. **Fase 4** — dashboard, relatórios, exportação.
5. **Fase 5** — RBAC, auditoria, Docker, CI/CD.

> O maior potencial do sistema não está no CSS — está na **modelagem do domínio
> e nas regras de negócio**. Mas nada disso importa enquanto a home dá erro 500
> no primeiro acesso: **bugs primeiro, produto depois.**
