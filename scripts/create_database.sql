-- Cria o banco de dados MySQL em branco para o Gestao de Frotas.
-- Rode este script uma unica vez, conectado ao MySQL como um usuario
-- com permissao para criar bancos (por exemplo o root):
--
--   mysql -u root -p < scripts/create_database.sql
--
-- Depois rode as migracoes do Django para criar as tabelas:
--
--   python manage.py migrate

CREATE DATABASE IF NOT EXISTS gestao_frotas
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- (Opcional) Cria um usuario dedicado para a aplicacao.
-- Descomente e troque a senha antes de usar:
--
-- CREATE USER IF NOT EXISTS 'frotas'@'localhost' IDENTIFIED BY 'troque_esta_senha';
-- GRANT ALL PRIVILEGES ON gestao_frotas.* TO 'frotas'@'localhost';
-- FLUSH PRIVILEGES;
