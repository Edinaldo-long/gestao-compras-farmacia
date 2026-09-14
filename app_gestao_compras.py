import os
import sys
import re
import socket
from datetime import datetime
import firebirdsql
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

DB_LOCAL = "192.168.100.108"
DB_REMOTO = "10.224.166.55"
DB_NAME = "3"
DB_USER = "SYSDBA"
DB_PASS = "masterkey"

# 5 itens por página
ITENS_POR_PAGINA = 5

# Cores ANSI
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
GRAY = "\033[90m"
RESET = "\033[0m"


def testar_porta(host, porta=3050, timeout=1.5):
    try:
        with socket.create_connection((host, porta), timeout=timeout):
            return True
    except Exception:
        return False


def obter_conexao():
    rotas = [(DB_LOCAL, "Local"), (DB_REMOTO, "VPN")]
    for host, nome in rotas:
        if testar_porta(host, 3050):
            try:
                con = firebirdsql.connect(
                    host=host,
                    port=3050,
                    database=DB_NAME,
                    user=DB_USER,
                    password=DB_PASS,
                    charset="WIN1252",
                    auth_plugin_name="Legacy_Auth",
                )
                return con
            except Exception:
                continue
    print(f"\n{RED}[ERRO] Nenhuma rota de conexao respondeu.{RESET}")
    sys.exit(1)


def parsear_entrada(entrada):
    txt = entrada.strip()
    if not txt:
        return (
            "AND CAST(M.DT_MOVIMENTO AS DATE) >= CURRENT_DATE - 60",
            "60d",
            60,
        )

    if txt.isdigit() and len(txt) <= 4:
        dias = int(txt)
        return (
            f"AND CAST(M.DT_MOVIMENTO AS DATE) >= CURRENT_DATE - {dias}",
            f"{dias}d",
            dias,
        )

    partes = re.findall(r"\d{2}/?\d{2}/?\d{4}", txt)

    def cvt(d):
        return datetime.strptime(d.replace("/", ""), "%d%m%Y")

    try:
        if len(partes) == 1:
            d1 = cvt(partes[0])
            dias = max(1, (datetime.now() - d1).days)
            return (
                f"AND CAST(M.DT_MOVIMENTO AS DATE) >= '{d1.strftime('%Y-%m-%d')}'",
                f">={d1.strftime('%d/%m')}",
                dias,
            )
        elif len(partes) >= 2:
            d1, d2 = cvt(partes[0]), cvt(partes[1])
            dias = max(1, (d2 - d1).days)
            return (
                f"AND CAST(M.DT_MOVIMENTO AS DATE) BETWEEN '{d1.strftime('%Y-%m-%d')}' AND '{d2.strftime('%Y-%m-%d')}'",
                f"{d1.strftime('%d/%m')}-{d2.strftime('%d/%m')}",
                dias,
            )
    except Exception:
        pass

    return (
        "AND CAST(M.DT_MOVIMENTO AS DATE) >= CURRENT_DATE - 60",
        "60d",
        60,
    )


def consultar_dados(con, clausula_data):
    sql = f"""
    SELECT 
        P.CD_PRODUTO,
        P.DS_PRODUTO,
        P.TP_UNIDADE,
        COALESCE((
            SELECT SUM(M.QT_MOVIMENTO) / 1000.0
            FROM T_PRODUTO_LOTE_MOV M
            WHERE M.CD_PRODUTO = P.CD_PRODUTO
              AND M.TP_MOVIMENTO = 'S'
              {clausula_data}
        ), 0) AS CONSUMO,
        CAST(COALESCE((
            SELECT SUM(L.QT_ESTOQUE) / 1000.0
            FROM T_PRODUTO_LOTE L
            WHERE L.CD_PRODUTO = P.CD_PRODUTO
              AND L.DT_VALIDADE >= CURRENT_DATE
              AND L.QT_ESTOQUE > 0
        ), 0) AS NUMERIC(15,2)) AS SALDO_BOM,
        CAST(COALESCE((
            SELECT SUM(L.QT_ESTOQUE) / 1000.0
            FROM T_PRODUTO_LOTE L
            WHERE L.CD_PRODUTO = P.CD_PRODUTO
              AND L.DT_VALIDADE < CURRENT_DATE
              AND L.QT_ESTOQUE > 0
        ), 0) AS NUMERIC(15,2)) AS SALDO_VENC
    FROM T_PRODUTO P
    WHERE P.CD_GRUPO = 1
      AND P.TP_PRODUTO = 'M'
      AND P.ID_SITUACAO = 'A'
    """
    cur = con.cursor()
    cur.execute(sql)
    return cur.fetchall()


def abreviar_unidade(unidade_str):
    u = (unidade_str or "").strip().upper()
    if "GRAMA" in u or u in ("GRA", "GR", "G"):
        return "GR"
    elif "KILO" in u or "QUILO" in u or u in ("KG", "KIL"):
        return "KG"
    elif "LITRO" in u or u in ("LIT", "LT", "L"):
        return "LT"
    elif "MILILITRO" in u or u == "ML":
        return "ML"
    elif "MILIGRAMA" in u or u == "MG":
        return "MG"
    return u[:2] if u else "--"


def analisar_item(s_bom, s_venc, consumo, dias_per, lt):
    tem_venc = s_venc > 0

    if consumo <= 0:
        if s_bom > 0:
            urg = 3
            st_icon = f"{MAGENTA}💤{RESET}"
            dur_str = "STOP"
            ideal = 0.0
            txt_st = "ADORMECIDO"
        else:
            urg = 5
            st_icon = f"{GRAY}•{RESET}"
            dur_str = "-"
            ideal = 0.0
            txt_st = "INATIVO"

        if tem_venc:
            st_icon += f"{RED}🗑️{RESET}"
            txt_st += "+LIXO"
        return urg, st_icon, dur_str, ideal, txt_st

    cmd = consumo / dias_per
    dias_rest = s_bom / cmd if cmd > 0 else 0

    est_ideal = cmd * (lt + 10)

    if dias_rest < lt:
        urg = 1
        st_icon = f"{RED}🚨{RESET}"
        txt_st = "URGENTE"
    elif dias_rest <= (lt + 15):
        urg = 2
        st_icon = f"{YELLOW}⚠️{RESET}"
        txt_st = "ATENCAO"
    elif dias_rest <= 150:
        urg = 4
        st_icon = f"{GREEN}📦{RESET}"
        txt_st = "OK"
    else:
        urg = 4
        st_icon = f"{CYAN}📈{RESET}"
        txt_st = "EXCESSO"

    if tem_venc:
        st_icon += f"{RED}🗑️{RESET}"
        txt_st += "+LIXO"

    dur_str = f"{int(dias_rest)}d" if dias_rest < 90 else f"{int(dias_rest//30)}m"
    return urg, st_icon, dur_str, est_ideal, txt_st


def formatar_numero(valor):
    if valor <= 0:
        return "-"
    if valor >= 1000:
        return f"{int(valor)}"
    if valor % 1 != 0:
        return f"{valor:.1f}"
    return f"{int(valor)}"


def gerar_pdf(dados, desc_per, lt, titulo_tipo="COMPRAS"):
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    arq = f"relatorio_{titulo_tipo.lower()}_{ts}.pdf"
    doc = SimpleDocTemplate(
        arq,
        pagesize=A4,
        rightMargin=12,
        leftMargin=12,
        topMargin=15,
        bottomMargin=15,
    )
    styles = getSampleStyleSheet()

    elem = [
        Paragraph(f"RELATÓRIO DE INSUMOS - {titulo_tipo}", styles["Heading2"]),
        Paragraph(
            f"Emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Hist: {desc_per} | LT: {lt}d | Total: {len(dados)} itens",
            styles["Normal"],
        ),
    ]

    tabela = [["Cod", "Descrição", "UN", "Saldo Bom", "Vencido", "Dur", "Est. Ideal"]]
    for d in dados:
        tabela.append([
            str(d["cod"]),
            d["nome"][:28],
            d["un"],
            f"{d['s_bom']:.2f}",
            f"{d['s_venc']:.2f}" if d["s_venc"] > 0 else "-",
            d["dur"],
            f"{d['ideal']:.2f}" if d["ideal"] > 0 else "-",
        ])

    t = Table(tabela, colWidths=[35, 210, 25, 65, 55, 50, 60])
    cor_header = "#B71C1C" if titulo_tipo == "COMPRAS" else "#4A148C"
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(cor_header)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ALIGN", (1, 1), (1, -1), "LEFT"),
            ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
        ])
    )

    elem.append(t)
    doc.build(elem)
    return arq


def limpar_tela():
    os.system("cls" if os.name == "nt" else "clear")


def main():
    limpar_tela()
    print(f"{CYAN}=== MONITOR DE ESTOQUE FARMACÊUTICO ==={RESET}")
    ent = input("Histórico [Enter = 60d]: ").strip()
    clausula_data, desc_per, dias_per = parsear_entrada(ent)

    lt_in = input("Lead Time / Entrega [Enter = 20d]: ").strip()
    lt = int(lt_in) if lt_in.isdigit() else 20

    con = obter_conexao()
    try:
        print("Consultando dados...")
        brutos = consultar_dados(con, clausula_data)
    finally:
        con.close()

    if not brutos:
        print("Nenhum dado retornado.")
        return

    itens = []
    for r in brutos:
        cd, nome, un_raw, consumo, s_bom, s_venc = r
        c_val = float(consumo or 0)
        sb_val = float(s_bom or 0)
        sv_val = float(s_venc or 0)

        un_compacta = abreviar_unidade(un_raw)

        if un_compacta == "GR" and (c_val > 50000 or sb_val > 50000):
            c_val /= 1000.0
            sb_val /= 1000.0
            sv_val /= 1000.0
            un_compacta = "KG"
        elif un_compacta in ("KG", "LT") and c_val > 10000:
            c_val /= 1000.0

        if c_val <= 0 and sb_val <= 0 and sv_val <= 0:
            continue

        urg, st_icon, dur_str, est_ideal, txt_st = analisar_item(
            sb_val, sv_val, c_val, dias_per, lt
        )

        # Código inteiro limpo (sem .0)
        try:
            cod_limpo = int(float(cd))
        except (ValueError, TypeError):
            cod_limpo = 0

        itens.append({
            "cod": cod_limpo,
            "cod_s": str(cod_limpo),
            "nome": (nome or "").strip(),
            "nome_u": (nome or "").strip().upper(),
            "un": un_compacta,
            "s_bom": sb_val,
            "s_venc": sv_val,
            "dur": dur_str,
            "st_icon": st_icon,
            "ideal": est_ideal,
            "urg": urg,
            "txt_st": txt_st,
            "tem_venc": sv_val > 0,
            "is_adormecido": (c_val <= 0 and sb_val > 0),
        })

    itens.sort(key=lambda x: (x["urg"], not x["tem_venc"], -x["ideal"], x["nome"]))

    modo = "criticos"
    termo = ""
    pag = 0

    while True:
        limpar_tela()

        if modo == "criticos":
            base = [i for i in itens if i["urg"] in (1, 2) or i["tem_venc"]]
            tag = f"{RED}🚨 COMPRAS / DESCARTE{RESET}"
        elif modo == "adormecidos":
            base = [i for i in itens if i["is_adormecido"]]
            tag = f"{MAGENTA}💤 ESTOQUE ADORMECIDO{RESET}"
        else:
            base = itens
            tag = f"{GREEN}📦 TODOS OS ITENS{RESET}"

        if termo:
            base = [i for i in base if termo in i["nome_u"] or termo in i["cod_s"]]

        total_pag = max(1, (len(base) + ITENS_POR_PAGINA - 1) // ITENS_POR_PAGINA)
        pag = min(pag, total_pag - 1)
        pag = max(0, pag)
        fatia = base[pag * ITENS_POR_PAGINA : (pag + 1) * ITENS_POR_PAGINA]

        print(f"[{tag}] {desc_per} | LT:{lt}d")
        print(f"Pág {pag+1}/{total_pag} ({len(base)} itens)")
        if termo:
            print(f"Filtro: '{termo}'")
        print("—" * 38)

        # Exibição: Código sem cerquilha e sem ponto flutuante
        for i in fatia:
            print(f"{CYAN}{i['cod']:<6}{RESET} {i['nome'][:18]:<18} {GRAY}{i['un']:>2}{RESET}")
            print(f"  {i['st_icon']} {i['dur']:<4} | Sld:{formatar_numero(i['s_bom']):>6} | Idl:{formatar_numero(i['ideal']):>6}")
            print("·" * 38)

        # Legenda
        print("Legenda:")
        print(f" {RED}🚨{RESET} Comprar   {YELLOW}⚠️{RESET} Atenção   {CYAN}📈{RESET} Excesso")
        print(f" {MAGENTA}💤{RESET} Parado    {GRAY}•{RESET} Inativo   {RED}🗑️{RESET} Descarte")
        print("—" * 38)

        # Menu
        print(" [Enter] Próx  | [v] Voltar | [s] Sair")
        print(" [c] Compras   | [z] Adorm  | [t] Todos")
        print(" [p] Gerar PDF | Ou DIGITE p/ buscar")
        print("—" * 38)

        cmd = input("Opção / Busca >> ").strip()

        if cmd == "":
            if pag + 1 < total_pag:
                pag += 1
        elif cmd.lower() == "v":
            if pag > 0:
                pag -= 1
        elif cmd.lower() == "c":
            modo = "criticos"
            termo = ""
            pag = 0
        elif cmd.lower() == "z":
            modo = "adormecidos"
            termo = ""
            pag = 0
        elif cmd.lower() == "t":
            modo = "todos"
            termo = ""
            pag = 0
        elif cmd.lower() == "p":
            titulo = "COMPRAS" if modo == "criticos" else ("ADORMECIDOS" if modo == "adormecidos" else "TODOS")
            arq = gerar_pdf(base, desc_per, lt, titulo_tipo=titulo)
            print(f"\n[OK] PDF gerado: {os.path.abspath(arq)}")
            input("Pressione Enter para voltar...")
        elif cmd.lower() == "s":
            print("\nEncerrado.")
            break
        else:
            termo = cmd.upper()
            pag = 0


if __name__ == "__main__":
    main()
