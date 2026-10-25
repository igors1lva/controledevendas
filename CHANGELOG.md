# 📜 Registro de Alterações (Changelog - Showcase / Portfólio)

Todas as alterações notáveis deste projeto serão documentadas neste arquivo.

## [1.5.0] - 2026-10-24 - Atualização Comercial & Interface

### ✨ Funcionalidades Adicionadas & Aprimoramentos
- **Ponto de Venda (PDV) - Agilidade com Bipagem Automática**:
  - Inclusão direta e instantânea no carrinho ao realizar a leitura de códigos de barras via leitor óptico USB.
  - Foco e retenção no leitor USB para bipagem sequencial de dezenas de itens em poucos segundos.
  - Tecla de atalho dedicada **F4** para inserção manual de produtos selecionados no catálogo.
  - Remoção de barras de rolagem cinzas poluentes na tela F2 (Nova Venda Balcão), preservando a navegação fluida via *mousewheel*.
- **Dashboard Analítico (BI) & Personalização Visual da Marca**:
  - Possibilidade de upload e personalização do logotipo oficial da empresa do cliente na tela inicial (480x160 px com validação e pré-visualização ao vivo).
  - Reposicionamento do botão do Dashboard no topo do menu lateral com destaque em verde esmeralda.
  - Gráficos nativos em Canvas: evolução temporal de vendas, faturamento por turno/horário, curva ABC de lucratividade e gráfico donut de distribuição dos pagamentos.
- **Tela de Descanso Inteligente (Screensaver 30s)**:
  - Detecção de inatividade de 30 segundos disparando overlay protetor de tela em fullscreen.
  - Suporte para o cliente definir uma imagem personalizada institucional ou utilizar a tela padrão oficial AstridSoft.
  - Retorno instantâneo ao ponto de operação a qualquer movimento de mouse ou pressionamento de tecla.
- **Design System, Menus Retráteis & Temas Aprimorados**:
  - Reorganização do menu lateral com seção expansível *"Configurações & Fiscal"* ocultando as sub-abas de forma organizada.
  - Software configurado para sempre inicializar no tema **Light** (Claro) por padrão.
  - Tema Claro enriquecido com contornos definidos em cards e tabelas para evitar fadiga visual e confusão com o fundo branco.
  - Logotipo AstridSoft (gatinho cyber) mantido com cores uniformes e fiéis em ambos os modos (Claro e Escuro).
  - Botão discreto de chavinha (`🔑`) no rodapé para alteração e renovação de licença.
  - Botão de acesso rápido a backup no Header HUD com alinhamento e espaçamento corrigidos (`🛡 Backup`).
- **Otimização de Desempenho**:
  - Redução drástica da latência nos campos de busca no catálogo, estoque e histórico de vendas com algoritmo de *debounce* refinado.
  - Troca ultrarrápida entre telas do sistema.

---

## [1.0.0] - 2026-09-26 - Lançamento Inicial

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
