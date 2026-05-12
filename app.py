from flask import Flask, request, jsonify
from flask_cors import CORS

import pdfplumber
import re
from typing import List, Dict, Optional

app = Flask(__name__)
CORS(app)

# ======================================
# CONFIG
# ======================================

INVALID_TICKERS = {
    "US","USD","ETF","INC","LLC","CORP","PLC","ADR",
    "NYSE","NASDAQ","CASH","TOTAL","SALDO","JUROS",
    "APORTES","DADOS","POR","DAS","DOS","E","OS",
    "AS","DA","DO","DE"
}

# ======================================
# HELPERS
# ======================================

def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_number(value: str) -> float:
    """
    Aceita:
    2.984,52
    2984,52
    2,984.52
    """
    try:
        value = value.replace("R$", "").replace("US$", "").strip()

        if "," in value and "." in value:
            # formato brasileiro
            value = value.replace(".", "").replace(",", ".")
        elif "," in value:
            value = value.replace(",", ".")

        return float(value)
    except:
        return 0.0


def parse_percent(value: str) -> Optional[float]:
    try:
        return float(value.replace("%", "").replace(",", "."))
    except:
        return None


def classify_asset(nome: str, moeda: str) -> str:
    nome = nome.upper()

    if moeda == "USD":
        return "Internacional"

    if re.match(r"^[A-Z]{4}\d{1,2}$", nome):
        return "Renda Variável"

    if "FII" in nome:
        return "Renda Variável"

    return "Renda Fixa"


def build_asset(ativo, valor, moeda, rentabilidade=None):
    return {
        "ativo": ativo,
        "valor": valor,
        "moeda": moeda,
        "classe": classify_asset(ativo, moeda),
        "rentabilidade": rentabilidade
    }

# ======================================
# XP PARSER (mantido simples)
# ======================================

def parse_xp(text: str) -> List[Dict]:

    assets = []

    lines = text.split("\n")

    for line in lines:

        if "R$" not in line:
            continue

        name_match = re.match(r"^(.*?)\s+R\$", line)
        value_match = re.search(r"R\$\s*([\d\.,]+)", line)

        if not name_match or not value_match:
            continue

        nome = name_match.group(1).strip()
        valor = parse_number(value_match.group(1))

        if valor <= 0:
            continue

        percents = re.findall(r"([\-\+]?\d+,\d+)%", line)

        rent = None
        if len(percents) >= 2:
            rent = parse_percent(percents[1])

        assets.append(build_asset(nome, valor, "BRL", rent))

    return assets

# ======================================
# 🔥 AVENUE PARSER CORRIGIDO
# ======================================

def parse_avenue(text: str) -> List[Dict]:

    assets = []

    text = text.replace("\r", "\n")
    lines = text.split("\n")

    for line in lines:

        line = normalize_spaces(line)

        # ignora linhas irrelevantes
        if len(line) < 20:
            continue

        if not any(x in line for x in ["ETF", "Stock", "Stocks", "ETF's"]):
            continue

        # pega ticker (palavra curta)
        ticker_match = re.search(r"\b([A-Z]{2,5})\b", line)

        if not ticker_match:
            continue

        ticker = ticker_match.group(1)

        if ticker in INVALID_TICKERS:
            continue

        # pega valores tipo 1.234,56
        values = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", line)

        if not values:
            continue

        # último número da linha = volume
        value_str = values[-1]

        valor = parse_number(value_str)

        if valor <= 0:
            continue

        assets.append(build_asset(ticker, valor, "USD"))

    return assets

# ======================================
# BTG PARSER (mantido)
# ======================================

def parse_btg(text: str) -> List[Dict]:

    assets = []

    matches = re.findall(r"([A-Z]{4,6}\d{0,2})\s+([\d\.]+,\d{2})", text)

    for ticker, val in matches:
        valor = parse_number(val)

        if valor > 0:
            assets.append(build_asset(ticker, valor, "BRL"))

    return assets

# ======================================
# DETECTOR
# ======================================

def detect_parser(text: str):

    t = text.upper()

    if "POSIÇÃO DETALHADA" in t:
        return parse_xp

    if "AVENUE" in t or "US$" in t or "ETF'S" in t:
        return parse_avenue

    if "RELATÓRIO DE PERFORMANCE" in t:
        return parse_btg

    return None

# ======================================
# EXTRAÇÃO
# ======================================

def extract_pdf_text(file):

    full = ""

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            txt = page.extract_text()
            if txt:
                full += txt + "\n"

    return full

# ======================================
# ROTA
# ======================================

@app.route("/upload", methods=["POST"])
def upload():

    files = request.files.getlist("files")

    all_assets = []

    for file in files:

        try:
            text = extract_pdf_text(file)

            parser = detect_parser(text)

            if not parser:
                continue

            assets = parser(text)

            all_assets.extend(assets)

        except Exception as e:
            print("Erro:", e)

    return jsonify({
        "ativos": all_assets
    })


if __name__ == "__main__":
    app.run(debug=True)
