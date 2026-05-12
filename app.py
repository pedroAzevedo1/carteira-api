from flask import Flask, request, jsonify
from flask_cors import CORS

import pdfplumber
import re

app = Flask(__name__)

CORS(app)

# ======================================================
# PARSERS AUXILIARES
# ======================================================

def parse_brl(valor):

    try:

        return float(
            valor
            .replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )

    except:
        return 0


def parse_usd(valor):

    try:

        return float(
            valor
            .replace("US$", "")
            .replace(",", "")
            .strip()
        )

    except:
        return 0


def parse_percent(valor):

    try:

        return float(
            valor
            .replace("%", "")
            .replace(",", ".")
            .strip()
        )

    except:
        return None

# ======================================================
# CLASSIFICAÇÃO
# ======================================================

def classificar(nome, moeda):

    nome = nome.upper()

    if moeda == "USD":
        return "Internacional"

    if re.match(r'^[A-Z]{4}\d{1,2}$', nome):
        return "Renda Variável"

    if "ETF" in nome:
        return "Internacional"

    if "FII" in nome:
        return "Renda Variável"

    return "Renda Fixa"

# ======================================================
# XP
# ======================================================

def parse_xp(text):

    data = []

    match = re.search(
        r'POSIÇÃO DETALHADA DOS ATIVOS(.*?)(Relatório informativo|$)',
        text,
        re.S
    )

    if not match:
        return data

    section = match.group(1)

    lines = section.split("\n")

    for line in lines:

        line = re.sub(r'\s+', ' ', line).strip()

        if any(x in line.upper() for x in [

            "TOTAL",
            "POSIÇÃO",
            "ESTRATÉGIA",
            "SALDO BRUTO",
            "RENT.",
            "%CDI",
            "MÊS ATUAL",
            "ANO",
            "24 MESES",
            "PÓS FIXADO",
            "FUNDOS LISTADOS",
            "CAIXA"

        ]):
            continue

        nome_match = re.match(
            r'^(.*?)\s+R\$',
            line
        )

        if not nome_match:
            continue

        nome = nome_match.group(1).strip()

        valor_match = re.search(
            r'R\$\s*([\d\.\,]+)',
            line
        )

        if not valor_match:
            continue

        valor = parse_brl(valor_match.group(1))

        if valor <= 0:
            continue

        percentuais = re.findall(
            r'([\-\+]?\d+,\d+)%',
            line
        )

        rent = None

        if len(percentuais) >= 2:
            rent = parse_percent(percentuais[1])

        data.append({

            "ativo": nome,
            "valor": valor,
            "moeda": "BRL",
            "classe": classificar(nome, "BRL"),
            "rentabilidade": rent

        })

    return data

# ======================================================
# AVENUE
# ======================================================

def parse_avenue(text):

    data = []

    # procura seção de posição consolidada
    match = re.search(

        r'Posição Consolidada(.*?)Diagnóstico da carteira',

        text,

        re.S
    )

    if not match:
        return data

    # pega ativos internacionais
    lines = text.split("\n")

    for line in lines:

        line = re.sub(r'\s+', ' ', line).strip()

        # exemplo:
        # TFLO iShares Treasury Floating Rate Bond ETF US$ 5,895.00

        ativo_match = re.match(
            r'^([A-Z]{1,10})\s+.*?US\$\s*([\d,]+\.\d+)',
            line
        )

        if not ativo_match:
            continue

        ticker = ativo_match.group(1)

        valor = parse_usd(
            ativo_match.group(2)
        )

        if valor <= 0:
            continue

        data.append({

            "ativo": ticker,
            "valor": valor,
            "moeda": "USD",
            "classe": "Internacional",
            "rentabilidade": None

        })

    return data

# ======================================================
# BTG / OPEN FINANCE
# ======================================================

def parse_btg(text):

    data = []

    # ==================================================
    # RENDA FIXA
    # ==================================================

    rf_section = re.search(

        r'Em Renda Fixa(.*?)(Em Previdência)',

        text,

        re.S
    )

    if rf_section:

        lines = rf_section.group(1).split("\n")

        for line in lines:

            line = re.sub(r'\s+', ' ', line).strip()

            ativo_match = re.match(
                r'^(.+?)\s+([\d\.]+,\d{2})',
                line
            )

            if not ativo_match:
                continue

            nome = ativo_match.group(1).strip()

            valor = parse_brl(
                ativo_match.group(2)
            )

            if valor <= 0:
                continue

            data.append({

                "ativo": nome,
                "valor": valor,
                "moeda": "BRL",
                "classe": "Renda Fixa",
                "rentabilidade": None

            })

    # ==================================================
    # RENDA VARIÁVEL
    # ==================================================

    rv_matches = re.findall(

        r'([A-Z]{4,6}\d{0,2})\s+\d+,\d+\s+R\$\s*([\d\.]+,\d{2})',

        text
    )

    for ticker, valor_str in rv_matches:

        valor = parse_brl(valor_str)

        if valor <= 0:
            continue

        data.append({

            "ativo": ticker,
            "valor": valor,
            "moeda": "BRL",
            "classe": "Renda Variável",
            "rentabilidade": None

        })

    # ==================================================
    # FUNDOS
    # ==================================================

    fundo_matches = re.findall(

        r'(KAPITALO.*?|BTG.*?FIRF.*?)\s+\d+,\d+\s+.*?R\$\s*([\d\.]+,\d{2})',

        text
    )

    for nome, valor_str in fundo_matches:

        valor = parse_brl(valor_str)

        if valor <= 0:
            continue

        data.append({

            "ativo": nome.strip(),
            "valor": valor,
            "moeda": "BRL",
            "classe": "Fundo",
            "rentabilidade": None

        })

    return data

# ======================================================
# CONSOLIDA
# ======================================================

def consolidar(lista):

    mapa = {}

    for item in lista:

        chave = f"{item['ativo']}_{item['moeda']}"

        if chave not in mapa:

            mapa[chave] = {

                **item,

                "somaRent":

                    item["rentabilidade"]
                    * item["valor"]

                    if item["rentabilidade"] is not None
                    else 0,

                "somaBase":

                    item["valor"]

                    if item["rentabilidade"] is not None
                    else 0
            }

        else:

            mapa[chave]["valor"] += item["valor"]

            if item["rentabilidade"] is not None:

                mapa[chave]["somaRent"] += (
                    item["rentabilidade"]
                    * item["valor"]
                )

                mapa[chave]["somaBase"] += (
                    item["valor"]
                )

    resultado = []

    for item in mapa.values():

        rent = (

            item["somaRent"]
            / item["somaBase"]

            if item["somaBase"] > 0
            else None
        )

        resultado.append({

            "ativo": item["ativo"],
            "valor": item["valor"],
            "moeda": item["moeda"],
            "classe": item["classe"],
            "rentabilidade": rent
        })

    return resultado

# ======================================================
# DETECTA RELATÓRIO
# ======================================================

def detectar_parser(text):

    if "POSIÇÃO DETALHADA DOS ATIVOS" in text:
        return parse_xp

    if "Avenue Securities" in text:
        return parse_avenue

    if "Relatório de Performance" in text:
        return parse_btg

    return None

# ======================================================
# API
# ======================================================

@app.route("/upload", methods=["POST"])

def upload():

    files = request.files.getlist("files")

    carteira = []

    for file in files:

        with pdfplumber.open(file) as pdf:

            texto = ""

            for page in pdf.pages:

                texto += (
                    page.extract_text()
                    or ""
                ) + "\n"

            parser = detectar_parser(texto)

            if parser:

                ativos = parser(texto)

                carteira.extend(ativos)

    ativos_consolidados = consolidar(carteira)

    return jsonify({

        "ativos": ativos_consolidados

    })

# ======================================================
# START
# ======================================================

if __name__ == "__main__":

    app.run(debug=True)
