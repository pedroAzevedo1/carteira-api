from flask import Flask, request, jsonify
from flask_cors import CORS

import pdfplumber
import re

app = Flask(__name__)

CORS(app)

# =========================================
# PARSERS
# =========================================

def parse_brl(valor):

    try:

        return float(

            valor
            .replace('.', '')
            .replace(',', '.')

        )

    except:

        return 0


def parse_percent(valor):

    try:

        return float(

            valor
            .replace('%', '')
            .replace(',', '.')

        )

    except:

        return None

# =========================================
# CLASSIFICAÇÃO
# =========================================

def classificar(nome, moeda):

    nome = nome.upper()

    if moeda == "USD":
        return "Internacional"

    if re.match(r'^[A-Z]{4}\d{1,2}$', nome):
        return "Renda Variável"

    if "FII" in nome or "ETF" in nome:
        return "Renda Variável"

    return "Renda Fixa"

# =========================================
# PARSER XP
# =========================================

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

        line = re.sub(
            r'\s+',
            ' ',
            line
        ).strip()

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

        # =================================
        # NOME
        # =================================

        nome_match = re.match(

            r'^(.*?)\s+R\$',

            line
        )

        if not nome_match:
            continue

        nome = nome_match.group(1).strip()

        # =================================
        # VALOR
        # =================================

        valor_match = re.search(

            r'R\$\s*([\d\.\,]+)',

            line
        )

        if not valor_match:
            continue

        valor = parse_brl(
            valor_match.group(1)
        )

        if valor <= 0:
            continue

        # =================================
        # PERCENTUAIS
        # =================================

        percentuais = re.findall(

            r'([\-\+]?\d+,\d+)%',

            line
        )

        # Estrutura:
        #
        # 0 -> peso
        # 1 -> rentabilidade mês
        # 2 -> %CDI
        # 3 -> rentabilidade ano

        rent = None

        if len(percentuais) >= 2:

            rent = parse_percent(
                percentuais[1]
            )

        data.append({

            "ativo": nome,
            "valor": valor,
            "moeda": "BRL",

            "classe": classificar(
                nome,
                "BRL"
            ),

            "rentabilidade": rent
        })

    return data

# =========================================
# CONSOLIDA
# =========================================

def consolidar(lista):

    mapa = {}

    for item in lista:

        chave = (
            item['ativo']
            + "_"
            + item['moeda']
        )

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

# =========================================
# API
# =========================================

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
                )

            ativos = parse_xp(texto)

            carteira.extend(ativos)

    ativos_consolidados = consolidar(carteira)

    return jsonify({

        "ativos":
            ativos_consolidados

    })

# =========================================
# START
# =========================================

if __name__ == "__main__":

    app.run(debug=True)
