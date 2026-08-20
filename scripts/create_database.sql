-- Cria o banco de dados PostgreSQL em branco para o Gestao de Frotas.
-- Rode este script uma unica vez, conectado ao PostgreSQL como um usuario
-- com permissao para criar bancos (por exemplo o postgres):
--
--   psql -U postgres -f scripts/create_database.sql
--
-- (No Windows/PowerShell funciona igual, pois nao usa redirecionamento.)
--
-- Depois rode as migracoes do Django para criar as tabelas:
--
--   python manage.py migrate
--
-- Observacao: o PostgreSQL nao suporta "CREATE DATABASE IF NOT EXISTS".
-- Se o banco ja existir, o comando abaixo apenas retorna um aviso.

CREATE DATABASE gestao_frotas
    ENCODING 'UTF8'
    TEMPLATE template0;

-- (Opcional) Cria um usuario dedicado para a aplicacao.
-- Descomente e troque a senha antes de usar:
--
-- CREATE USER frotas WITH PASSWORD 'troque_esta_senha';
-- GRANT ALL PRIVILEGES ON DATABASE gestao_frotas TO frotas;
