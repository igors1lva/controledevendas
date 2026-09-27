-- ============================================================================
-- SCRIPT DE POPULAÇÃO DEMONSTRATIVA (SEED DE DEMONSTRAÇÃO)
-- Arquivo: seed.demo.sql
-- 
-- Autor: Igor Fernando
-- Ano: 2026
-- Finalidade: Demonstração e Portfólio (Dados 100% fictícios)
-- Uso: sqlite3 gestao_vendas.db < seed.demo.sql
-- ============================================================================

-- 1. CONFIGURAÇÕES BÁSICAS DA EMPRESA MODELO
INSERT INTO configuracoes (chave, valor) VALUES 
    ('appearance_mode', 'Dark'),
    ('fiscal_modo_emissao', 'NAO_FISCAL'),
    ('fiscal_cnpj', '00.000.000/0001-00'),
    ('fiscal_ie', '000000000000'),
    ('fiscal_razao_social', 'Empresa Modelo Demonstrativa LTDA'),
    ('fiscal_nome_fantasia', 'Mercado & Conveniência Modelo'),
    ('fiscal_crt', '1'),
    ('fiscal_ambiente', '2'),
    ('fiscal_uf', 'SP'),
    ('fiscal_ibge_uf', '35'),
    ('fiscal_serie', '1'),
    ('fiscal_ultimo_numero', '100'),
    ('fiscal_acbr_host', '127.0.0.1'),
    ('fiscal_acbr_porta', '3434'),
    ('fiscal_csc_id', '000001'),
    ('fiscal_csc_token', 'DEMO-TOKEN-SEFAZ-HOMOLOGACAO-0001')
ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor;

-- 2. CATÁLOGO DEMONSTRATIVO DE PRODUTOS
INSERT INTO produtos (id, nome, preco, preco_custo, estoque, data_cadastro, codigo_barras, ncm, cest, cfop, unidade) VALUES
    (1, 'Café Torrado e Moído Gourmet 500g', 18.90, 11.50, 150, '2026-09-01 08:00:00', '7891000100011', '09012100', '1709600', '5102', 'UN'),
    (2, 'Azeite de Oliva Extra Virgem 500ml', 36.50, 24.00, 120, '2026-09-01 08:00:00', '7891000100028', '15091000', '1704900', '5102', 'UN'),
    (3, 'Arroz Nobre Tipo 1 Pacote 5kg', 28.90, 20.20, 200, '2026-09-01 08:00:00', '7891000100035', '10063021', '1700100', '5102', 'PCT'),
    (4, 'Feijão Carioca Selecionado 1kg', 8.50, 5.20, 180, '2026-09-01 08:00:00', '7891000100042', '07133210', '1700200', '5102', 'KG'),
    (5, 'Refrigerante Tradicional 2 Litros', 10.50, 6.80, 250, '2026-09-01 08:00:00', '7891000100059', '22021000', '0301000', '5405', 'UN'),
    (6, 'Leite Integral UHT Longa Vida 1L', 5.60, 3.80, 300, '2026-09-01 08:00:00', '7891000100066', '04012010', '1701900', '5102', 'UN'),
    (7, 'Achocolatado em Pó Instantâneo 400g', 11.90, 7.30, 140, '2026-09-01 08:00:00', '7891000100073', '18069000', '1708800', '5102', 'UN'),
    (8, 'Biscoito Recheado Chocolate 130g', 3.90, 2.20, 280, '2026-09-01 08:00:00', '7891000100080', '19053100', '1705600', '5102', 'UN'),
    (9, 'Detergente Lava-Louças Neutro 500ml', 2.80, 1.45, 320, '2026-09-01 08:00:00', '7891000100097', '34022000', '1100100', '5102', 'FR'),
    (10, 'Sabonete Hidratante Suave 90g', 3.20, 1.60, 260, '2026-09-01 08:00:00', '7891000100103', '34011190', '2004800', '5102', 'UN'),
    (11, 'Água Mineral sem Gás Garrafa 500ml', 2.50, 0.90, 400, '2026-09-01 08:00:00', '7891000100110', '22011000', '0300100', '5102', 'UN'),
    (12, 'Pão de Forma Tradicional 500g', 7.90, 4.50, 110, '2026-09-01 08:00:00', '7891000100127', '19059090', '1706000', '5102', 'PCT')
ON CONFLICT(id) DO UPDATE SET
    nome = excluded.nome,
    preco = excluded.preco,
    preco_custo = excluded.preco_custo,
    estoque = excluded.estoque,
    codigo_barras = excluded.codigo_barras,
    ncm = excluded.ncm,
    cest = excluded.cest,
    cfop = excluded.cfop,
    unidade = excluded.unidade;

-- 3. TRANSAÇÕES DEMONSTRATIVAS RECENTES (VENDAS SIMULADAS)
INSERT INTO vendas (id, produto_id, produto_nome, quantidade, preco_unitario, valor_total, data_hora, status) VALUES
    (1, 1, 'Café Torrado e Moído Gourmet 500g', 2, 18.90, 37.80, '2026-09-27 10:15:22', 'CONCLUIDA'),
    (2, 2, 'Azeite de Oliva Extra Virgem 500ml', 1, 36.50, 36.50, '2026-09-27 10:20:45', 'CONCLUIDA'),
    (3, 5, 'Refrigerante Tradicional 2 Litros', 3, 10.50, 31.50, '2026-09-27 10:45:10', 'CONCLUIDA'),
    (4, 3, 'Arroz Nobre Tipo 1 Pacote 5kg', 1, 28.90, 28.90, '2026-09-27 11:02:30', 'CONCLUIDA'),
    (5, 6, 'Leite Integral UHT Longa Vida 1L', 4, 5.60, 22.40, '2026-09-27 11:30:15', 'CONCLUIDA')
ON CONFLICT(id) DO UPDATE SET
    produto_id = excluded.produto_id,
    produto_nome = excluded.produto_nome,
    quantidade = excluded.quantidade,
    preco_unitario = excluded.preco_unitario,
    valor_total = excluded.valor_total,
    data_hora = excluded.data_hora,
    status = excluded.status;
