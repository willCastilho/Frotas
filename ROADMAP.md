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

## 🟠 Fase 2 — Fundação de código

Deixar a base pronta para crescer sem virar bagunça.

- [ ] 🟡 **Camada de Forms** — criar `carro/forms.py` com `VeiculoForm` e
  `CustoForm` (`ModelForm`). Elimina a validação manual espalhada nas views,
  valida tipos de graça (valor negativo, ano fora da faixa, data inválida) e
  remove a duplicação entre "novo" e "editar".
- [ ] 🟡 **Organizar as views** — dividir `carro_views.py` por domínio
  (`views/veiculos.py`, `views/custos.py`, `views/dashboard.py`…). Usar
  Class-Based Views (List/Create/Update/Delete) **onde reduzem repetição** —
  sem forçar CBV em views com muita regra de negócio.
- [ ] 🟠 **Resolver o N+1 de queries** — a home chama `custo_mes_atual()`,
  `custo_mes_anterior()` e `comparacao_custos()` por veículo (várias queries
  cada). Trocar por `annotate` + `Sum`/`Case` para calcular em 1–2 queries.
- [ ] 🟡 **Paginação** na listagem de veículos (`Paginator`).
- [ ] 🟡 **Testes básicos** — cobrir os cálculos de custo
  (`custo_mes_atual`, `comparacao_custos`) e o fluxo de criação de veículo/custo.
- [ ] 🔵 **Limpeza de modelo** — padronizar nomes (`Data_compra` → `data_compra`)
  e remover o campo `Show`, que não é usado. Requer migração.

---

## 🟢 Fase 3 — Modelagem de domínio (a parte de maior valor)

Aqui o sistema deixa de ser "CRUD de veículo" e vira gestão de frota de verdade.
**Um item por vez**, cada um com tela e teste.

- [ ] **Abastecimento como entidade própria** — em vez de tratar combustível
  como um "custo" genérico:
  ```
  Abastecimento: veiculo, data, quilometragem, litros,
                 valor_total, valor_litro, posto, tipo_combustivel
  ```
  Habilita **consumo médio (km/l)**, **preço médio do litro** e
  **custo de combustível por km**.
- [ ] **Histórico de quilometragem** — registrar leituras de odômetro ao longo
  do tempo (`RegistroQuilometragem: veiculo, data, quilometragem, origem`) em
  vez de um único número. Base para km/mês, custo/km e detecção de
  inconsistências.
- [ ] **Manutenção preventiva com alerta** — controlar por km e/ou por data
  (troca de óleo, licenciamento, seguro) com status visual
  🟢 em dia · 🟡 próximo · 🔴 atrasado.
- [ ] **Situação do veículo mais rica** — além de ativo/inativo/manutenção,
  contemplar `vendido` / `baixado` para permitir indicadores corretos.
- [ ] 🔵 **Dados cadastrais adicionais** — placa (única), Renavam, chassi,
  combustível, quilometragem atual — **conforme forem sendo usados**, não todos
  de uma vez.

---

## 📊 Fase 4 — Camada gerencial

Só faz sentido **depois** que os dados ricos da Fase 3 existirem (dashboard sem
dados é gráfico vazio).

- [ ] **Dashboard inicial** — cards de resumo (veículos ativos, custo do mês,
  em manutenção) + gráfico de custos dos últimos meses + ranking de veículos
  por custo.
- [ ] **Relatórios** — custos por veículo/período/categoria, consumo de
  combustível, quilometragem, veículos mais caros.
- [ ] **Exportação** — CSV/Excel (e PDF se necessário). Exportar dados é quase
  tão importante quanto cadastrá-los em um sistema administrativo.
- [ ] **Filtros e busca avançada** na listagem (marca, status, faixa de ano).

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
