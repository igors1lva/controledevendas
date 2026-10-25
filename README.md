# 🛍️ Central de Vendas & PDV - Sistema de Gestão Comercial (Showcase / Portfólio v1.5.0)

> **Versão Pública de Demonstração (Portfólio v1.5.0)**  
> **Desenvolvedor:** Igor Fernando  
> **Ano:** 2026  
> **Licença:** Proprietária / Portfólio (consulte o arquivo [`LICENSE`](file:///c:/Users/igorf/Downloads/soft%20para%20cadastro/LICENSE))

---

## 📌 Sobre o Projeto

O **Central de Vendas** é uma solução desktop comercial completa e de alto desempenho projetada para automação de checkout (PDV), controle de inventário em tempo real com leitor óptico USB, inteligência analítica de negócios (BI), fechamento diário auditado com criptografia SHA-256 e geração automatizada de relatórios em Excel protegidos por senha.

Desenvolvido em **Python 3** com uma interface moderna e ergonômica baseada em **CustomTkinter**, adota padrões de arquitetura em camadas, persistência transacional ACID (SQLite), arquitetura *offline-first* e compatibilidade multi-edição (Não-Fiscal, Fiscal NFC-e SEFAZ e Híbrida Completa).

---

## 🛡️ Nota de Sanitização e Segurança (Showcase Público)

Para publicação e exibição no portfólio do GitHub, este repositório foi **integralmente sanitizado**:
- **Desacoplamento de Segredos:** Chaves privadas de autoridade, certificados digitais SEFAZ (A1 `.pfx`), senhas mestras de produção, CNPJs de clientes e dados comerciais de terceiros foram 100% omitidos ou substituídos por dados modelo.
- **Camada de Abstração de Licença (`DemoKeyValidator` / `LicenseServiceMock`):** A implementação real com criptografia assimétrica de curva elíptica Ed25519 e vinculação de hardware (Machine ID) foi isolada. No showcase público, o validador opera com bypass transparente ou aceita chaves de teste no formato genérico:
  ```text
  DEMO-2026-XXXX-XXXX  (exemplo: DEMO-2026-A1B2-C3D4)
  ```
- **Execução Imediata:** O sistema inicia diretamente no modo de demonstração documentado (*"Modo de demonstração ativado para fins de portfólio"*), permitindo avaliação imediata por recrutadores e clientes sem barreiras de ativação.

---

## 🚀 Principais Módulos do Sistema & Novidades v1.5.0

### 1. 🛒 Ponto de Venda Inteligente (PDV - Frente de Caixa Ágil)
- **Bipagem com Inclusão Automática no Carrinho:** Leitura direta de códigos de barras (EAN-13 / GTIN) via leitor óptico USB. Ao bipar um produto, ele é adicionado instantaneamente ao carrinho de compras sem necessidade de cliques manuais, mantendo o foco pronto para o próximo item.
- **Fluxo Contínuo e Atalho F2:** O operador de caixa pode bipar múltiplos itens sequencialmente e pressionar a tecla **F2** para abrir o modal de pagamento, calcular o troco e finalizar a venda.
- **Atalho F4 Dedicado:** Padronizado exclusivamente para inserção manual rápida no carrinho (`🛒 + Adicionar ao Carrinho (F4)`).
- **Interface Limpa sem Barras de Rolagem:** Remoção de barras de rolagem visuais poluentes nos cards de checkout, mantendo a navegação vertical suave por rodinha do mouse (*mousewheel*).
- **Validação Atômica de Estoque:** Atualização imediata em tempo real impedindo transações com estoque insuficiente.
- **Múltiplos Meios de Pagamento:** Suporte a Dinheiro, Cartão de Débito, Cartão de Crédito, Pix e Vale Alimentação.

### 2. 📊 Business Intelligence (BI) & Dashboard Analítico
- **Logotipo Customizado da Empresa do Cliente:** Recurso nativo para upload do logotipo institucional da empresa na tela inicial (proporção oficial 480x160 px com validação de dimensões e pré-visualização ao vivo).
- **Botão do Dashboard em Destaque:** Elevado no topo do menu lateral com destaque em verde esmeralda.
- **Gráficos Nativos em Canvas:**
  - Evolução temporal de vendas e receita diária.
  - Gráfico *Donut* de distribuição dos métodos de pagamento utilizados.
  - Curva ABC de produtos com ranking de lucratividade e margem comercial apurada.
  - Mapa de horários de pico (Manhã, Tarde, Noite).
- **Filtros Dinâmicos:** Consulta por *Hoje*, *Últimos 7 Dias*, *Últimos 30 Dias*, *Mês Atual* ou *Histórico Completo*.

### 3. 💤 Tela de Descanso Inteligente (Screensaver 30s)
- **Detecção de Inatividade:** Acionamento automático de protetor de tela em tela cheia após 30 segundos sem movimentação de mouse ou teclas.
- **Customização pelo Cliente:** Opção para o usuário carregar sua própria imagem corporativa de descanso (JPG/PNG) ou manter a tela padrão temática AstridSoft.
- **Retorno Instantâneo:** Desativação imediata ao menor toque no mouse ou teclado, sem travar a interface.

### 4. 🎨 Design System, Menus Retráteis & Temas Aprimorados
- **Menu Lateral Acordeão:** Estrutura expansível por categorias com a seção *"Configurações & Fiscal"* agrupando as sub-abas de maneira limpa.
- **Inicialização Padrão Light:** O software foi configurado para inicializar sempre no tema Claro por padrão.
- **Contraste Aprimorado no Modo Light:** Linhas, bordas e colunas com contorno reforçado para evitar confusão visual com o fundo branco.
- **Identidade AstridSoft (Gatinho Cyber):** Logotipo oficial com renderização em cor uniforme e fiel tanto no modo Claro quanto no modo Escuro.
- **Gestão Discreta de Licença:** Botão de chavinha (`🔑`) no rodapé lateral para consulta e renovação rápida da licença.
- **Header HUD Otimizado:** Relógio em tempo real, status da conexão SQLite e botão rápido de backup (`🛡 Backup`) com alinhamento e espaçamento perfeitos.

### 5. 📦 Gestão de Inventário, Catálogo & XML
- Cadastro completo de mercadorias com NCM, CEST, CFOP, Unidade de Medida, Preço de Custo, Preço de Venda e Margem de Lucro calculada.
- Busca instantânea e otimizada por palavras-chave com *debounce*, sem travamentos ao digitar.
- Importação rápida de catálogo a partir de arquivos XML de NF-e com pré-visualização modal.

### 6. 📈 Fechamento de Caixa Auditado & Relatórios Excel
- Encerramento de turno diário com cálculo de CMV (Custo das Mercadorias Vendidas), faturamento bruto e lucro líquido.
- Geração automatizada de planilhas formatadas no Microsoft Excel (`.xlsx`) com carimbo de data/hora exclusivo e proteção por senha de administrador.
- Assinatura digital com hash de integridade criptográfica **SHA-256**.

---

## 📁 Arquitetura do Repositório

```text
├── app.py                   # Orquestrador da janela principal, HUD, menu acordeão e navegação
├── database.py              # Camada de persistência SQLite com transações seguras e migrações
├── license_manager.py       # Abstração de licença (DemoKeyValidator / LicenseServiceMock)
├── keygen.py                # Gerador demonstrativo de chaves no padrão DEMO-2026-XXXX-XXXX
├── reports.py               # Consolidação analítica e exportação em Excel protegido
├── theme.py                 # Design System (paleta de cores Dark/Light, contornos e tipografia)
├── backup_manager.py        # Central de backup atômico e rotina diária em background
├── edicao_config.py         # Configuração de perfil de edição (Não-Fiscal, Fiscal, Completa)
├── clipboard_utils.py       # Utilitários seguros para manipulação da área de transferência
├── seed.demo.sql            # Script SQL com catálogo de produtos e configurações fictícias
├── seed_demo.py             # Utilitário para popular o banco de demonstração
├── xml_importer.py          # Módulo de importação de catálogo a partir de XML de NF-e
├── assets/                  # Identidade visual (ícone, logotipos e screensaver)
│   ├── astridsoft_logo.png       # Logotipo oficial AstridSoft (gatinho cyber)
│   ├── astridsoft_screensaver.png# Tela de descanso institucional padrão
│   ├── logo.png                  # Logotipo geral da aplicação
│   └── vendas.ico                # Ícone em alta resolução da aplicação
├── views/                   # Telas e componentes desacoplados da interface (CustomTkinter)
│   ├── pos_sale_view.py          # Frente de Caixa PDV com bipagem USB e atalho F2/F4
│   ├── dashboard_view.py         # Dashboard Analítico (BI) com upload de logo do cliente
│   ├── screensaver_overlay.py    # Overlay fullscreen da tela de descanso de 30 segundos
│   ├── backup_modal.py           # Central de backup instantâneo, exportação e restauração
│   ├── payment_modal.py          # Modal de fechamento de venda e seleção de pagamento
│   ├── cash_closure_modal.py     # Modal de fechamento de caixa e conferência de turno
│   ├── catalog_view.py           # Catálogo interativo de produtos com busca otimizada
│   ├── inventory_view.py         # Listagem e gestão de inventário
│   ├── product_form_view.py      # Formulário de cadastro/edição de produtos
│   ├── fiscal_config_view.py     # Configuração de parâmetros fiscais e contingência
│   ├── export_excel_view.py      # Central de relatórios e exportação
│   └── license_modal.py          # Modal de ativação e conformidade de licença
├── fiscal/                  # Módulo de integração fiscal NFC-e
│   ├── fiscal_service.py         # Facade do serviço fiscal com contingência automática
│   ├── acbr_adapter.py           # Conector TCP Socket para ACBrMonitorPLUS
│   ├── nfce_builder.py           # Construtor de leiaute fiscal 4.00 e cálculo de chave de acesso
│   └── sync_worker.py            # Thread em background para sincronização silenciosa
└── LICENSE                  # Termos de licença proprietária para fins de portfólio
```

---

## 🛠️ Como Executar o Projeto Localmente

### 1. Clonar o Repositório e Instalar Dependências
```bash
git clone <URL_DO_REPOSITORIO>
cd "soft para cadastro"
pip install -r requirements.txt
```

### 2. Popular o Banco com Dados Demonstrativos
Para carregar um catálogo modelo com produtos e configurações pré-definidas:
```bash
python seed_demo.py
```
*(Alternativamente: `sqlite3 gestao_vendas.db < seed.demo.sql`)*

### 3. Executar a Aplicação
```bash
python app.py
```
> O sistema iniciará imediatamente no modo de demonstração documentado no tema Claro (Light). Caso deseje testar a ativação manual de chaves, utilize qualquer código no padrão `DEMO-2026-XXXX-XXXX` ou gere um novo executando `python keygen.py`.

---

## 📦 Compilação do Executável (.exe)

Para compilar um executável único para Windows utilizando o PyInstaller:
```powershell
python -m PyInstaller --noconfirm --onefile --windowed --name "CentralDeVendas" --add-data "assets;assets" --collect-all customtkinter app.py
```
Ou utilize o script de automação:
```cmd
build_exe.bat
```

---

## 📄 Termos de Uso e Licença

```text
Copyright (c) 2026 Igor Fernando. All Rights Reserved.

This source code is made available solely for demonstration and portfolio purposes.
No permission is granted to copy, compile, run, modify, distribute, or use this
software, in whole or in part, for personal or commercial purposes without explicit
written permission from the author.
```
