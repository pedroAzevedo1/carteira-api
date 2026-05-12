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
    app.run(debug=True)

    app.run(debug=True)
