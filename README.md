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
- MySQL
- Pillow (upload de imagens)

## 📋 Pré-requisitos

- Python 3.12+
- MySQL 8.0+ instalado e rodando
- No Linux, para compilar o `mysqlclient` pode ser necessário:
  `sudo apt install pkg-config default-libmysqlclient-dev build-essential`

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

### 4. Crie o banco de dados MySQL (em branco)

Rode o script SQL para criar o banco vazio:

```bash
mysql -u root -p < scripts/create_database.sql
```

> O script apenas **cria o banco em branco**. As tabelas são criadas pelo
> Django no passo 6, através das migrações.

### 5. Configure as variáveis de ambiente

Copie o arquivo de exemplo e ajuste com os dados do seu MySQL:

```bash
cp .env.example .env
```

Edite o `.env` preenchendo `DB_PASSWORD` (e o que mais precisar).

### 6. Rode as migrações (cria as tabelas no banco)

```bash
python manage.py migrate
```

### 7. (Opcional) Crie um usuário administrador

```bash
python manage.py createsuperuser
```

### 8. Inicie o servidor

```bash
python manage.py runserver
```

Acesse: http://127.0.0.1:8000/ — e o admin em http://127.0.0.1:8000/admin/

## 📁 Estrutura do projeto

```
gestao-frotas/
├── carro/               # App principal (frota)
│   ├── base/static/css/ # Estilos
│   ├── migrations/      # Migrações do banco
│   ├── templates/       # Templates HTML
│   ├── views/           # Views
│   ├── admin.py
│   ├── models.py        # Modelos Veiculo e Custo
│   └── urls.py
├── project/             # Configuração do Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── media/               # Uploads de imagens dos veículos
├── scripts/
│   └── create_database.sql
├── .env.example
├── manage.py
└── requirements.txt
```

## 🔒 Segurança

- O arquivo `.env` (com senhas e `SECRET_KEY`) **não é versionado**.
- Em produção, gere uma `SECRET_KEY` nova e defina `DJANGO_DEBUG=False`.
