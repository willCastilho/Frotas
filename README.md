# 🚗 Gestão de Frotas

Sistema web em **Django** para gerenciamento de uma frota de veículos e o
controle de custos de cada um (combustível, manutenção, seguro, IPVA, multas
e outros). Permite cadastrar veículos, registrar despesas, acompanhar o custo
do mês atual e comparar com o mês anterior.

## ✨ Funcionalidades

- Cadastro, edição e exclusão de veículos (com foto)
- Filtro por status (ativo, inativo, em manutenção) e busca por marca/modelo
- Registro de custos por veículo, classificados por tipo
- Cálculo automático do custo do mês atual e do mês anterior
- Indicador visual de variação de custos (subiu / caiu / estável)
- Painel administrativo do Django

## 🛠️ Tecnologias

- Python 3.12
- Django 5.2
- PostgreSQL
- Pillow (upload de imagens)

## 📋 Pré-requisitos

- Python 3.12+
- PostgreSQL 14+ instalado e rodando
- O driver `psycopg2-binary` já vem como wheel pré-compilado (não precisa de
  compilador). No Linux, se optar por compilar do fonte, instale `libpq-dev`.

## 🚀 Como rodar o projeto

### 1. Clone o repositório

```bash
git clone https://github.com/willCastilho/gestao-frotas.git
cd gestao-frotas
```

### 2. Crie e ative um ambiente virtual

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux / macOS
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Crie o banco de dados PostgreSQL (em branco)

Rode o script SQL para criar o banco vazio:

```bash
psql -U postgres -f scripts/create_database.sql
```

> No **Windows/PowerShell** o comando é o mesmo (não usa redirecionamento `<`).
> Se preferir, dá para criar direto: `createdb -U postgres gestao_frotas`.
>
> O script apenas **cria o banco em branco**. As tabelas são criadas pelo
> Django no passo 6, através das migrações.

### 5. Configure as variáveis de ambiente

Copie o arquivo de exemplo e ajuste com os dados do seu PostgreSQL:

```bash
cp .env.example .env
```

Edite o `.env` preenchendo `DB_PASSWORD` (e o que mais precisar).

### 6. Rode as migrações (cria as tabelas no banco)

```bash
python manage.py migrate
```

### 7. Crie um usuário (necessário para entrar)

O sistema exige login. Crie um usuário administrador:

```bash
python manage.py createsuperuser
```

### 8. Inicie o servidor

```bash
python manage.py runserver
```

Acesse: http://127.0.0.1:8000/ — você será redirecionado para a tela de login
(`/accounts/login/`). O admin fica em http://127.0.0.1:8000/admin/

### 9. (Opcional) Crie os grupos de acesso

Perfis prontos: **Administrador**, **Gestor**, **Operador** e **Consulta**.

```bash
python manage.py criar_grupos
```

Depois associe cada usuário a um grupo pelo admin do Django.

## ✅ Rodando os testes

```bash
python manage.py test
```

A cada push/PR os testes também rodam automaticamente no GitHub Actions
(`.github/workflows/ci.yml`), contra um PostgreSQL real.

## 🐳 Rodando com Docker

Sobe a aplicação (Gunicorn) e o PostgreSQL já configurados:

```bash
docker compose up --build
```

A aplicação fica em http://localhost:8000/. As variáveis podem ser ajustadas por
um `.env` na raiz (veja `.env.example`).

## ☁️ Deploy no Railway

O projeto já está pronto para o [Railway](https://railway.app) (build por
`Dockerfile`, `PORT` automática, estáticos via WhiteNoise e leitura de
`DATABASE_URL`).

1. **Novo projeto** → *Deploy from GitHub repo* → selecione `willCastilho/Frotas`.
2. Adicione um serviço **PostgreSQL** (*New → Database → PostgreSQL*).
3. No serviço da aplicação, aba **Variables**, defina:
   - `DATABASE_URL` = `${{Postgres.DATABASE_URL}}` (referência ao Postgres)
   - `DJANGO_SECRET_KEY` = uma chave longa e aleatória
   - `DJANGO_DEBUG` = `False`
   - `DJANGO_ALLOWED_HOSTS` = o domínio gerado, ex.: `meuapp.up.railway.app`
   - `DJANGO_CSRF_TRUSTED_ORIGINS` = `https://meuapp.up.railway.app`
4. O deploy roda `migrate` automaticamente no start. Para criar o usuário
   administrador, use o terminal do serviço no Railway:
   ```bash
   python manage.py createsuperuser
   python manage.py criar_grupos   # opcional
   ```

> As migrações rodam sozinhas a cada deploy (definido no `Dockerfile` /
> `railway.json`). O banco do Railway já vem criado — não precisa de `createdb`.

## 🔐 Auditoria

Todas as alterações em veículos, custos, abastecimentos, quilometragem e planos
de manutenção são registradas via **django-auditlog** (quem alterou, o quê e
quando). Os registros ficam visíveis no admin do Django.

## 💾 Backup do banco

```bash
./scripts/backup.sh /caminho/para/backups
```

Gera um dump `.sql.gz` com data no nome. Pode ser agendado no cron.

## 📁 Estrutura do projeto

```
gestao-frotas/
├── carro/                  # App principal (frota)
│   ├── base/static/css/    # Estilos
│   ├── management/commands # Comando criar_grupos
│   ├── migrations/         # Migrações do banco
│   ├── templates/          # Templates HTML
│   ├── views/              # Views (veiculos, custos, frota, dashboard, relatorios)
│   ├── admin.py
│   ├── apps.py             # Registro da auditoria
│   ├── forms.py            # ModelForms
│   ├── models.py           # Veiculo, Custo, Abastecimento, RegistroKm, PlanoManutencao
│   ├── tests.py            # 27 testes
│   └── urls.py
├── project/                # Configuração do Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── media/                  # Uploads de imagens dos veículos
├── scripts/
│   ├── create_database.sql
│   └── backup.sh
├── .github/workflows/ci.yml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── manage.py
├── ROADMAP.md
└── requirements.txt
```

## 🔒 Segurança

- O arquivo `.env` (com senhas e `SECRET_KEY`) **não é versionado**.
- Em produção, gere uma `SECRET_KEY` nova e defina `DJANGO_DEBUG=False`.
