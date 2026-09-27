# 🛍️ Central de Vendas & PDV - Sistema de Gestão Comercial (Showcase / Portfólio)

> **Versão Pública de Demonstração (Portfólio)**  
> **Desenvolvedor:** Igor Fernando  
> **Ano:** 2026  
> **Licença:** Proprietária / Portfólio (consulte o arquivo [`LICENSE`](file:///c:/Users/igorf/Downloads/soft%20para%20cadastro/LICENSE))

---

## 📌 Sobre o Projeto

O **Central de Vendas** é uma solução desktop comercial robusta e responsiva para Windows, projetada para automação de checkout (PDV), controle de inventário em tempo real, fechamento diário auditado e geração automatizada de relatórios em Excel com proteção criptográfica.

A aplicação foi desenvolvida em **Python 3** com interface moderna baseada em **CustomTkinter**, adotando padrões de arquitetura em camadas, persistência transacional ACID (SQLite) e arquitetura offline-first.

---

## 🛡️ Nota de Sanitização e Segurança (Showcase Público)

Para publicação e exibição no portfólio do GitHub, este repositório foi **integralmente sanitizado**:
- **Desacoplamento de Segredos:** Chaves privadas, certificados digitais SEFAZ (A1 `.pfx`), senhas reais, CNPJs de clientes e dados comerciais de terceiros foram 100% omitidos ou substituídos por dados modelo.
- **Camada de Abstração de Licença (`DemoKeyValidator` / `LicenseServiceMock`):** A implementação real com criptografia assimétrica de curva elíptica Ed25519 e chaves mestras de autoridade foi isolada. No showcase público, o validador aceita chaves de teste no formato genérico:
  ```text
  DEMO-2026-XXXX-XXXX  (exemplo: DEMO-2026-A1B2-C3D4)
  ```
  Além disso, o sistema conta com um bypass de demonstração documentado (*"Modo de demonstração ativado para fins de portfólio"*) para execução direta por recrutadores e avaliadores.

---

## 🚀 Principais Módulos do Sistema

### 1. 🛒 Ponto de Venda (PDV - Frente de Caixa)
- **Operação de Venda em Alta Performance:** Processamento transacional com latência média inferior a 15ms por transação.
- **Validação de Estoque:** Atualização atômica imediata impedindo vendas de produtos esgotados.
- **Múltiplas Formas de Pagamento:** Suporte a Dinheiro, Cartão de Débito, Cartão de Crédito, Pix e Vale Alimentação.
- **Modo Dual (Controle Interno / NFC-e Fiscal):** Alternância entre Cupom de Balcão e emissão fiscal via ACBrMonitor com contingência offline automática (`tpEmis = 9`).

### 2. 📦 Gestão de Inventário e Catálogo
- Cadastro completo de produtos com NCM, CEST, CFOP, Unidade de Medida, Preço de Custo, Preço de Venda e Margem de Lucro calculada.
- Busca em tempo real com leitor de código de barras (EAN-13 / GTIN).
- Indicadores visuais dinâmicos de nível de estoque (*Normal*, *Baixo* e *Esgotado*).

### 3. 📊 Relatórios Consolidados e Auditoria Digital (Excel)
- Exportação automatizada de relatórios diários (`relatorio_vendas_YYYY-MM-DD.xlsx`) via `openpyxl`.
- Fechamento auditado do dia com selo de integridade criptográfica **SHA-256**.
- Proteção criptográfica de planilhas comerciais via biblioteca `msoffcrypto`.

### 4. 🔐 Gerenciador de Chaves de Demonstração (`keygen.py`)
- Emissão de chaves demonstrativas nos padrões `DEMO-2026-XXXX-XXXX` tanto via interface gráfica (CustomTkinter) quanto via CLI.

---

## 📁 Arquitetura do Repositório

```text
├── app.py                   # Ponto de entrada, inicializador e orquestrador principal
├── database.py              # Camada de persistência SQLite com transações seguras e migrações
├── license_manager.py       # Abstração de licença (DemoKeyValidator / LicenseServiceMock)
├── keygen.py                # Gerador demonstrativo de chaves no padrão DEMO-2026-XXXX-XXXX
├── reports.py               # Consolidação analítica e exportação em Excel protegido
├── theme.py                 # Design System (paleta de cores Dark/Light e tipografia)
├── seed.demo.sql            # Script SQL com catálogo de produtos e configurações fictícias
├── seed_demo.py             # Utilitário para popular o banco de demonstração
├── xml_importer.py          # Módulo de importação de catálogo a partir de XML de NF-e
├── views/                   # Telas e componentes desacoplados da interface (CustomTkinter)
│   ├── pos_sale_view.py     # Tela de Checkout e Frente de Caixa
│   ├── inventory_view.py    # Listagem e gestão de inventário
│   ├── product_form_view.py # Formulário de cadastro/edição de produtos
│   ├── fiscal_config_view.py# Configuração de parâmetros fiscais e contingência
│   ├── daily_closure_view.py# Painel de Fechamento Diário e Auditoria SHA-256
│   ├── export_excel_view.py # Central de relatórios e exportação
│   └── license_modal.py     # Modal de ativação e conformidade de licença
├── fiscal/                  # Módulo de integração fiscal NFC-e
│   ├── fiscal_service.py    # Facade do serviço fiscal com contingência automática
│   ├── acbr_adapter.py      # Conector TCP Socket para ACBrMonitorPLUS
│   ├── nfce_builder.py      # Construtor de leiaute fiscal 4.00 e cálculo de chave de acesso
│   └── sync_worker.py       # Thread em background para sincronização silenciosa
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
Para carregar um catálogo modelo com 12 produtos e configurações pré-definidas:
```bash
python seed_demo.py
```
*(Alternativamente: `sqlite3 gestao_vendas.db < seed.demo.sql`)*

### 3. Executar a Aplicação
```bash
python app.py
```
> O sistema iniciará imediatamente no modo de demonstração documentado. Caso deseje testar a ativação manual de chaves, utilize qualquer código no padrão `DEMO-2026-XXXX-XXXX` ou gere um novo executando `python keygen.py`.

---

## 📦 Compilação do Executável (.exe)

Para compilar um executável único para Windows utilizando o PyInstaller:
```powershell
python -m PyInstaller --noconfirm --onefile --windowed --name "CentralDeVendas" --add-data "assets;assets" --collect-all customtkinter app.py
```
Ou execute o script automatizado:
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
