# 📜 Registro de Alterações (Changelog)

Todas as alterações notáveis deste projeto serão documentadas neste arquivo.

## [1.0.0] - 2026-09-26

### ✨ Funcionalidades Adicionadas
- **Módulo de Ponto de Venda (PDV)**:
  - Registro de vendas com busca rápida e seleção de produtos.
  - Abatimento automático de estoque e transações atômicas em SQLite.
  - Painel com resumo financeiro diário e listagem das últimas transações.
  - Impressão e geração de comprovante / termo não fiscal.
- **Módulo de Inventário & Catálogo**:
  - Cadastro, edição rápida e exclusão segura de produtos.
  - Indicadores visuais de status (*Em Estoque*, *Baixo Estoque* e *Esgotado*).
  - Importação de produtos via arquivo XML de NF-e com pré-visualização.
- **Módulo de Relatórios & Fechamento de Caixa**:
  - Exportação detalhada e estilizada de vendas para Microsoft Excel (`.xlsx`).
  - Fechamento auditado diário com totalizadores por forma de pagamento.
  - Histórico completo de vendas com filtros e exportação.
- **Sistema de Licenciamento Criptográfico**:
  - Chaves assimétricas Ed25519 (`admin_private.pem` e `public_key.pem`).
  - Suporte a planos de 30, 60, 90 dias e Vitalício (LIFETIME).
  - Proteção contra retrocesso de relógio do sistema (*Anti-Clock Tampering*).
  - Gerador de licenças dedicado (`keygen.py` com interface e CLI).
- **Instalador e Distribuição**:
  - Script Inno Setup (`installer.iss`) para instalação profissional no Windows.
  - Scripts PyInstaller (`GestaoVendas.spec`, `Keygen_Admin.spec`, `build_exe.bat`).
  - Suporte a ícones customizados (`venda.ico` e `assets/`).
