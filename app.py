from flask import Flask, request, jsonify
from flask_cors import CORS

import pdfplumber
import re
from typing import List, Dict, Optional

# ======================================================
# CONFIG
# ======================================================

app = Flask(__name__)
CORS(app)

# ======================================================
# CONSTANTES
# ======================================================

INVALID_TICKERS = {
    "US",
    "USD",
    "ETF",
    "INC",
    "LLC",
    "CORP",
    "PLC",
    "ADR",
    "NYSE",
    "NASDAQ",
    "CASH",
    "TOTAL",
    "SALDO",
    "JUROS",
    "APORTES",
    "DADOS",
    "POR",
    "DAS",
    "DOS",
    "E",
    "OS",
    "AS",
    "DA",
    "DO",
    "DE"
}

XP_IGNORE_TERMS = {
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
}

# ======================================================
# HELPERS
# ======================================================


def normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()



def parse_brl(value: str) -> float:
    try:
        cleaned = (
            value
            .replace("R$", "")
            .replace(".", "")
            .replace(",", ".")
            .strip()
        )

        return float(cleaned)

    except Exception:
        return 0.0



def parse_usd(value: str) -> float:
    try:
        cleaned = (
            value
            .replace("US$", "")
            .replace(",", "")
            .strip()
        )

        return float(cleaned)

    except Exception:
        return 0.0



def parse_percent(value: str) -> Optional[float]:
    try:
        cleaned = (
            value
            .replace("%", "")
            .replace(",", ".")
            .strip()
        )

        return float(cleaned)

    except Exception:
        return None



def classify_asset(name: str, currency: str) -> str:
    upper_name = name.upper()

    if currency == "USD":
        return "Internacional"

    if re.match(r"^[A-Z]{4}\d{1,2}$", upper_name):
        return "Renda Variável"

    if "FII" in upper_name:
        return "Renda Variável"

    if "ETF" in upper_name:
        return "Internacional"

    return "Renda Fixa"



def build_asset(
    ativo: str,
    valor: float,
    moeda: str,
    rentabilidade: Optional[float] = None,
    classe: Optional[str] = None
) -> Dict:

    return {
        "ativo": ativo,
        "valor": valor,
        "moeda": moeda,
        "classe": classe or classify_asset(ativo, moeda),
        "rentabilidade": rentabilidade
    }

# ======================================================
# XP PARSER
# ======================================================


def parse_xp(text: str) -> List[Dict]:

    assets = []

    match = re.search(
        r"POSIÇÃO DETALHADA DOS ATIVOS(.*?)(Relatório informativo|$)",
        text,
        re.S
    )

    if not match:
        return assets

    section = match.group(1)

    for raw_line in section.split("\n"):

        line = normalize_spaces(raw_line)
        upper_line = line.upper()

        if any(term in upper_line for term in XP_IGNORE_TERMS):
            continue

        name_match = re.match(r"^(.*?)\s+R\$", line)

        if not name_match:
            continue

        value_match = re.search(r"R\$\s*([\d\.,]+)", line)

        if not value_match:
            continue

        asset_name = name_match.group(1).strip()
        asset_value = parse_brl(value_match.group(1))

        if asset_value <= 0:
            continue

        percentages = re.findall(r"([\-\+]?\d+,\d+)%", line)

        profitability = None

        # XP:
        # 0 = peso
        # 1 = rentabilidade

        if len(percentages) >= 2:
            profitability = parse_percent(percentages[1])

        assets.append(
            build_asset(
                ativo=asset_name,
                valor=asset_value,
                moeda="BRL",
                rentabilidade=profitability
            )
        )

    return assets

# ======================================================
# AVENUE PARSER
# ======================================================


def parse_avenue(text: str) -> List[Dict]:

    assets = []

    normalized_text = normalize_spaces(text.upper())

    matches = re.findall(
        r"(?<![A-Z])([A-Z]{1,5})(?![A-Z])\s+[^$]{0,120}?US\$\s*([\d,]+\.\d{2})",
        normalized_text
    )

    found_assets = {}

    for ticker, value_string in matches:

        ticker = ticker.strip()

        if ticker in INVALID_TICKERS:
            continue

        if len(ticker) > 5:
            continue

        value = parse_usd(value_string)

        if value <= 0:
            continue

        if value < 1:
            continue

        if ticker not in found_assets:
            found_assets[ticker] = value
        else:
            found_assets[ticker] = max(found_assets[ticker], value)

    for ticker, value in found_assets.items():

        assets.append(
            build_asset(
                ativo=ticker,
                valor=value,
                moeda="USD",
                classe="Internacional"
            )
        )

    return assets

# ======================================================
# BTG PARSER
# ======================================================


def parse_btg(text: str) -> List[Dict]:

    assets = []

    equity_matches = re.findall(
        r"([A-Z]{4,6}\d{0,2})\s+([\d\.]+,\d{2})",
        text
    )

    for ticker, value_string in equity_matches:

        value = parse_brl(value_string)

        if value <= 0:
            continue

        assets.append(
            build_asset(
                ativo=ticker,
                valor=value,
                moeda="BRL",
                classe="Renda Variável"
            )
        )

    fund_matches = re.findall(
        r"(KAPITALO.*?|BTG.*?FIRF.*?)\s+([\d\.]+,\d{2})",
        text
    )

    for fund_name, value_string in fund_matches:

        value = parse_brl(value_string)

        if value <= 0:
            continue

        assets.append(
            build_asset(
                ativo=fund_name.strip(),
                valor=value,
                moeda="BRL",
                classe="Fundo"
            )
        )

    return assets

# ======================================================
# CONSOLIDAÇÃO
# ======================================================


def consolidate_assets(assets: List[Dict]) -> List[Dict]:

    grouped_assets = {}

    for asset in assets:

        key = f"{asset['ativo']}_{asset['moeda']}"

        if key not in grouped_assets:

            grouped_assets[key] = {
                "ativo": asset["ativo"],
                "valor": 0,
                "moeda": asset["moeda"],
                "classe": asset["classe"],
                "somaRent": 0,
                "somaBase": 0
            }

        grouped_assets[key]["valor"] += asset["valor"]

        profitability = asset.get("rentabilidade")

        if profitability is not None:

            grouped_assets[key]["somaRent"] += (
                profitability * asset["valor"]
            )

            grouped_assets[key]["somaBase"] += asset["valor"]

    consolidated = []

    for asset in grouped_assets.values():

        profitability = None

        if asset["somaBase"] > 0:

            profitability = (
                asset["somaRent"] / asset["somaBase"]
            )

        consolidated.append({
            "ativo": asset["ativo"],
            "valor": asset["valor"],
            "moeda": asset["moeda"],
            "classe": asset["classe"],
            "rentabilidade": profitability
        })

    return consolidated

# ======================================================
# DETECTOR
# ======================================================


def detect_parser(text: str):

    upper_text = text.upper()

    if "POSIÇÃO DETALHADA DOS ATIVOS" in upper_text:
        return parse_xp

    if any(keyword in upper_text for keyword in [
        "AVENUE",
        "NYSE",
        "NASDAQ",
        "US$",
        "DIAGNÓSTICO DA CARTEIRA"
    ]):
        return parse_avenue

    if "RELATÓRIO DE PERFORMANCE" in upper_text:
        return parse_btg

    return None

# ======================================================
# PDF EXTRACTION
# ======================================================


def extract_pdf_text(file) -> str:

    full_text = ""

    with pdfplumber.open(file) as pdf:

        for page in pdf.pages:

            extracted_text = page.extract_text(
                x_tolerance=2,
                y_tolerance=2,
                layout=False
            )

            if extracted_text:
                full_text += extracted_text + "\n"

    return full_text

# ======================================================
# ROUTES
# ======================================================


@app.route("/upload", methods=["POST"])
def upload():

    files = request.files.getlist("files")

    all_assets = []

    for file in files:

        try:

            text = extract_pdf_text(file)

            print("\n================ PDF ================\n")
            print(text[:5000])

            parser = detect_parser(text)

            if not parser:
                print("Nenhum parser detectado")
                continue

            extracted_assets = parser(text)

            print("\nATIVOS ENCONTRADOS:")
            print(extracted_assets)

            all_assets.extend(extracted_assets)

        except Exception as error:

            print(f"Erro ao processar arquivo: {error}")

    consolidated_assets = consolidate_assets(all_assets)

    return jsonify({
        "ativos": consolidated_assets
    })

# ======================================================
# START
# ======================================================

if __name__ == "__main__":
    app.run(debug=True)

