# Gestão de Frotas — Documentação Técnica

Sistema web **multi-tenant** para gestão de frota de veículos e controle de
custos, manutenção e documentação.

- **Stack:** Python 3.12 · Django 5.2 · PostgreSQL
- **Arquitetura:** SaaS multi-tenant (isolamento por organização)
- **Cobertura:** 74 testes automatizados

> Versão visual (com fluxograma e diagramas): publicada como Artifact no Claude Code.

---

## 1. Visão geral

O sistema permite a uma organização cadastrar seus veículos e **motoristas** e
acompanhar, de forma centralizada, os **custos** (avulsos, recorrentes ou
parcelados), **abastecimentos**, **quilometragem**, **manutenções preventivas**
e **documentos** de cada veículo. A partir desses dados, calcula indicadores
gerenciais (consumo médio, custo por km, custo por categoria, **depreciação e
patrimônio da frota**), projeta o fechamento do mês e emite alertas de
manutenção e de vencimento de documentos e de CNH.

Cada motorista pode ser **vinculado a um veículo por período**, o que permite
saber quem estava em qual veículo em qualquer data.

É **multi-tenant**: cada organização vê apenas os próprios dados, com controle
de acesso por papéis — adequado tanto para uso interno quanto para venda (SaaS).

## 2. Atores e perfis (RBAC por organização)

| Papel | Descrição | Permissões |
|---|---|---|
| Visitante | Não autenticado | Cadastro, login, recuperação de senha, páginas legais |
| Administrador | Dono da conta | Tudo: usuários, papéis, plano e dados da frota |
| Gestor | Operação da frota | Cria/edita/visualiza dados; recebe alertas |
| Operador | Registro do dia a dia | Lança custos, abastecimentos e manutenção |
| Consulta | Somente leitura | Visualiza dados, dashboard e relatórios |

## 3. Fluxograma de uso

```mermaid
flowchart TD
    A([Visitante]) --> B{Já tem conta?}
    B -- não --> C[Cadastro<br/>cria a organização]
    B -- sim --> D[Login]
    C --> E{Possui organização?}
    D --> E
    E -- não --> F[Criar organização]
    F --> G[Dashboard]
    E -- sim --> G[Dashboard<br/>KPIs, agenda 90 dias, projeção, patrimônio]
    G --> H[Cadastrar/editar veículos]
    G --> I[Lançar custos e abastecimentos]
    G --> J[Registrar km e manutenção]
    G --> K[Cadastrar documentos]
    G --> N[Cadastrar motoristas<br/>e vincular a veículos]
    H --> L[Alertas e indicadores]
    I --> L
    J --> L
    K --> L
    N --> L
    L --> M([Relatórios e exportação<br/>CSV, Excel, PDF, e-mail])
```

## 4. Arquitetura de implantação

```mermaid
flowchart LR
    NAV[Navegador] -- HTTPS --> APP[Aplicação Django<br/>Gunicorn + WhiteNoise<br/>multi-tenant, RBAC, auditoria]
    APP --> DB[(PostgreSQL)]
    APP --> S3[Armazenamento S3/R2<br/>fotos e comprovantes]
    APP --> MAIL[E-mail<br/>API HTTP Brevo ou SMTP]
    APP --> SEN[Sentry]
    GH[GitHub] --> CI[CI - GitHub Actions<br/>74 testes] --> APP
```

A aplicação é **stateless**: o estado vive no PostgreSQL e os arquivos no
armazenamento externo, permitindo escalar em múltiplos contêineres.

## 5. Modelo de dados

```mermaid
erDiagram
    PLANO ||--o{ ORGANIZACAO : possui
    ORGANIZACAO ||--o{ PERFILUSUARIO : tem
    ORGANIZACAO ||--o{ VEICULO : tem
    ORGANIZACAO ||--o{ MOTORISTA : tem
    VEICULO ||--o{ CUSTO : registra
    VEICULO ||--o{ ABASTECIMENTO : registra
    VEICULO ||--o{ REGISTROQUILOMETRAGEM : registra
    VEICULO ||--o{ PLANOMANUTENCAO : possui
    VEICULO ||--o{ DOCUMENTO : possui
    VEICULO ||--o{ ATRIBUICAOVEICULO : "tem motorista"
    MOTORISTA ||--o{ ATRIBUICAOVEICULO : "dirige"
    ABASTECIMENTO ||--|| CUSTO : "gera custo de combustível"
```

**Custos recorrentes/parcelados** compartilham um `grupo` e carregam
`parcela_numero`/`parcela_total`. **AtribuicaoVeiculo** liga Motorista e Veículo
por um período (`data_inicio`/`data_fim`); em aberto, define o motorista atual.

A **Organização** é a raiz do isolamento: como todo registro depende de um
Veículo, e o Veículo pertence a uma Organização, cada consulta é filtrada pela
conta do usuário.

## 6. Requisitos funcionais

Prioridade: **Alta** essencial · **Média** importante · **Baixa** desejável.

### Autenticação e conta
| ID | Requisito | Prioridade |
|---|---|---|
| RF-01 | Cadastro autosserviço (usuário + organização + perfil admin), com aceite LGPD | Alta |
| RF-02 | Login e logout | Alta |
| RF-03 | Recuperação de senha por e-mail (link com expiração) | Alta |
| RF-04 | Onboarding: usuário sem organização é direcionado a criar uma | Alta |
| RF-05 | Convidar usuários: link de definição de senha exibido na tela (funciona sem SMTP) e também enviado por e-mail | Média |
| RF-06 | Definir/alterar papel de cada usuário | Média |
| RF-07 | Remover usuários (exceto a si mesmo) | Baixa |
| RF-08 | Página da conta (organização, plano, assinatura) | Média |

### Multi-tenancy, planos e cobrança
| ID | Requisito | Prioridade |
|---|---|---|
| RF-09 | Isolar dados por organização | Alta |
| RF-10 | Controle de acesso por papéis (bloqueio de escrita para Consulta) | Alta |
| RF-11 | Associar organização a um plano com limite de veículos | Média |
| RF-12 | Impedir cadastro de veículo ao atingir o limite do plano | Média |
| RF-13 | Indicar status da assinatura (em dia/pendente) | Baixa |

### Veículos
| ID | Requisito | Prioridade |
|---|---|---|
| RF-14 | CRUD de veículos | Alta |
| RF-15 | Cadastro completo: marca, modelo, ano, cor, placa, Renavam, chassi, combustível, data/valor de aquisição, foto, status, observações, meta de custo | Alta |
| RF-16 | Busca por marca/modelo/placa e filtro por status | Média |
| RF-17 | Paginação da listagem | Baixa |

### Custos, abastecimentos e quilometragem
| ID | Requisito | Prioridade |
|---|---|---|
| RF-18 | CRUD de custos (tipo, descrição, valor, data, km, fornecedor, forma de pagamento) | Alta |
| RF-19 | Anexar comprovante (foto/PDF) ao custo | Média |
| RF-20 | Combustível como fonte única (abastecimento gera o custo, sem contagem dupla) | Alta |
| RF-21 | Registrar abastecimentos (data, km, litros, valor, posto, tipo) | Alta |
| RF-22 | Calcular consumo médio (km/l), custo/km e preço/litro | Alta |
| RF-23 | Histórico de quilometragem e km atual derivado | Média |
| RF-43 | Custos recorrentes/parcelados: parcelado divide o valor; mensal/anual repete (IPVA, seguro, licenciamento) | Média |

### Manutenção e documentos
| ID | Requisito | Prioridade |
|---|---|---|
| RF-24 | Planos de manutenção por km e/ou data, com status (em dia/próxima/atrasada) | Alta |
| RF-25 | Documentos com vencimento e status (vencido/vence em breve/em dia) | Alta |

### Dashboard e relatórios
| ID | Requisito | Prioridade |
|---|---|---|
| RF-26 | KPIs (veículos, ativos, em manutenção, custo do período) | Alta |
| RF-27 | Projeção de fechamento do mês | Média |
| RF-28 | Gráfico de custos dos últimos 6 meses | Média |
| RF-29 | Custos por categoria | Média |
| RF-30 | Ranking de veículos por custo | Baixa |
| RF-31 | Painel vertical dos próximos 90 dias: documentos, manutenções por data e manutenções em alerta por km (consolida os alertas de manutenção) | Alta |
| RF-32 | Patrimônio da frota: valor de aquisição × valor estimado atual (depreciação) | Média |
| RF-33 | Relatórios por categoria e por veículo com filtro de período | Média |
| RF-34 | Exportar custos em CSV, Excel e PDF | Média |
| RF-44 | Depreciação estimada do veículo (saldo decrescente) no detalhe | Média |
| RF-45 | Filtros de período no dashboard (mês atual/anterior, 3 meses, ano, intervalo customizado) | Média |

### Alertas, auditoria e conformidade
| ID | Requisito | Prioridade |
|---|---|---|
| RF-35 | Alertar quando o custo do mês estourar a meta do veículo | Média |
| RF-36 | Enviar alertas por e-mail (manutenção, documentos, orçamento), agendável | Média |
| RF-37 | Auditoria das alterações (quem, o quê, quando) | Média |
| RF-38 | Termos de Uso e Política de Privacidade (LGPD) com consentimento | Alta |

### Motoristas
| ID | Requisito | Prioridade |
|---|---|---|
| RF-39 | CRUD de motoristas (nome, CPF, CNH, categoria, validade, contato, status) | Alta |
| RF-40 | Alerta de validade da CNH (vencida/vence em breve/em dia) | Média |
| RF-41 | Vincular motorista a veículo por período; troca encerra o vínculo anterior | Alta |
| RF-42 | Relatório de qual motorista estava em qual veículo em uma data, com exportação CSV | Alta |

## 7. Requisitos não funcionais

| ID | Categoria | Requisito |
|---|---|---|
| RNF-01 | Segurança | Autenticação obrigatória; CSRF; hash de senha (PBKDF2); CSRF trusted origins em HTTPS; isolamento multi-tenant em todas as queries |
| RNF-02 | Autorização | Papéis; Consulta não altera dados; só admin gerencia usuários/plano |
| RNF-03 | Privacidade | LGPD: consentimento, minimização de dados, páginas legais |
| RNF-04 | Desempenho | Índices (Custo.data/veículo, Documento.vencimento, Veículo.org/status); agregações contra N+1; paginação |
| RNF-05 | Escalabilidade | Multi-tenant; contêineres stateless; mídia em S3/R2 |
| RNF-06 | Disponibilidade | Docker + Gunicorn; migrações no boot; deploy contínuo (Railway) |
| RNF-07 | Observabilidade | Sentry (opcional) e logging |
| RNF-08 | Backup | Rotina pg_dump agendável |
| RNF-09 | Manutenibilidade | Apps Django separados; 74 testes; CI (GitHub Actions) |
| RNF-10 | Portabilidade | Config por variáveis de ambiente (12-factor); `DATABASE_URL` |
| RNF-11 | Usabilidade | Tema escuro responsivo; feedback; confirmação em exclusões |
| RNF-12 | Internacionalização | pt-BR; fuso America/Sao_Paulo |
| RNF-13 | Integridade | Placa única por organização; combustível fonte única; cascatas coerentes |
| RNF-14 | Compatibilidade | Navegadores modernos; PostgreSQL 14+; Python 3.12 |
| RNF-15 | Entrega de e-mail | API HTTP do Brevo (HTTPS/443, imune a bloqueio de SMTP) com fallback para SMTP e console; envio tolerante a falha (não quebra o cadastro) |

## 8. Regras de negócio

- **Fonte única de combustível:** o abastecimento cria/mantém o custo de combustível; excluí-lo remove o custo.
- **Placa única por organização:** não se repete dentro da mesma conta.
- **Km atual derivado:** maior leitura entre abastecimentos e registros de km.
- **Status de manutenção:** combina km e data, escolhendo o mais crítico.
- **Status de documento:** vencido / vence em breve (≤30 dias) / em dia.
- **Status de CNH:** mesma regra dos documentos, sobre a validade da CNH.
- **Alerta de orçamento:** verde ≤80%, amarelo ≤100%, vermelho acima da meta.
- **Limite de plano:** o cadastro respeita o limite de veículos do plano.
- **Custos recorrentes/parcelados:** parcelado divide o valor em N parcelas mensais (ajustando o arredondamento na última); mensal/anual repete o mesmo valor.
- **Depreciação:** saldo decrescente de 10% ao ano sobre o valor de aquisição.
- **Vínculo de motorista:** ao abrir um novo vínculo para um veículo, o vínculo anterior em aberto é encerrado automaticamente (troca de motorista, sem sobreposição).

## 9. Stack e tecnologias

| Camada | Tecnologia |
|---|---|
| Linguagem / framework | Python 3.12 · Django 5.2 |
| Banco de dados | PostgreSQL (psycopg2 / dj-database-url) |
| Servidor | Gunicorn · WhiteNoise |
| Mídia | FileSystem (dev) · S3/R2 via django-storages (prod) |
| E-mail | API HTTP Brevo · SMTP · console (dev) |
| Auditoria | django-auditlog |
| Monitoramento | Sentry (opcional) |
| Relatórios | CSV nativo · Excel (openpyxl) · PDF (reportlab) |
| Implantação | Docker · Railway · GitHub Actions |

## 10. Pendências e evolução

Concluído recentemente: **módulo de motoristas** (cadastro, CNH, vínculo
motorista × veículo por período e relatório por data), **custos
recorrentes/parcelados**, **depreciação e patrimônio da frota**, **relatório em
PDF**, **filtros de período no dashboard**, **convite por link + e-mail** e
**entrega de e-mail pela API HTTP do Brevo**.

Em aberto:

- **Gateway de pagamento** (Stripe / Mercado Pago) com webhook de assinatura.
- **Agendador dos alertas por e-mail** (cron diário chamando `enviar_alertas`).
- **OCR de comprovantes/notas** (leitura automática do cupom) — depois, IA.
- **2FA** e limite de tentativas de login.
