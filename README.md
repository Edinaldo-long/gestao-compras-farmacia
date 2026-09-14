# 📦 Monitor de Estoque & Gestão de Compras Farmacêuticas

Sistema em Python com interface CLI (linha de comando) otimizada para dispositivos móveis via **Termux** (Android). Conecta-se diretamente ao banco de dados **Firebird SQL** para monitoramento em tempo real do giro de estoque, previsão de falta (Lead Time), detecção de produtos vencidos/parados e geração de relatórios em PDF.

---

## 🚀 Funcionalidades

- **Layout Mobile-First (Termux):** Exibição em duas linhas por item, adaptada para telas estreitas e leitura confortável com fontes grandes no celular.
- **Failover Automático de Conexão:** Alterna automaticamente entre a rede interna (Local) e a rede externa (VPN).
- **Classificação Inteligente por Status:**
  - 🚨 **Comprar:** Itens com cobertura abaixo do Lead Time de entrega.
  - ⚠️ **Atenção:** Itens próximos do ponto de reposição.
  - 📈 **Excesso:** Estoque muito acima do giro planejado.
  - 💤 **Adormecido:** Produtos com saldo em estoque sem movimentação recente.
  - 🗑️ **Descarte:** Detecção de lotes vencidos para descarte regulatório.
- **Busca Rápida:** Filtro dinâmico por código do produto ou descrição.
- **Exportação para PDF:** Geração de relatórios formatados prontos para envio ao setor de compras.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3.x
- **Banco de Dados:** Firebird SQL (`firebirdsql`)
- **Geração de Documentos:** ReportLab (`reportlab`)
- **Ambiente de Execução:** Termux (Android)

---

## 📲 Instalação no Termux

1. **Atualizar pacotes e instalar dependências básicas:**
   ```bash
   pkg update && pkg upgrade -y
   pkg install python git -y

Instalar as bibliotecas Python necessárias:
   pip install firebirdsql reportlab

Clonar o repositório:
   git clone [https://github.com/Edinaldo-long/gestao-compras-farmacia.git](https://github.com/Edinaldo-long/gestao-compras-farmacia.git)

Executar o programa:
   python app_gestao_compras.py
cd gestao-compras-farmacia
