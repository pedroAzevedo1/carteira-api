from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re

app = Flask(__name__)
CORS(app)

# ======================
# UTIL
# ======================
def parse_brl(v):
    try:
        return float(v.replace('.', '').replace(',', '.'))
    except:
        return 0

def parse_usd(v):
    try:
        return float(v.replace(',', ''))
    except:
        return 0

def parse_percent(v):
    try:
        return float(v.replace(',', '.').replace('%', ''))
    except:
        return None

# ======================
# CLASSIFICAÇÃO
# ======================
def classificar(nome, moeda):
    nome = nome.upper()

    if moeda == "USD":
        return "Internacional"

    if re.match(r'^[A-Z]{4}\d{1,2}$', nome):
        return "Renda Variável"

    if "FII" in nome or "ETF" in nome:
        return "Renda Variável"

    return "Renda Fixa"

# ======================
# PARSER XP
# ======================
def parse_xp(text):
    data = []

    if "POSIÇÃO DETALHADA DOS ATIVOS" not in text:
        return data

    section = text.split("POSIÇÃO DETALHADA DOS ATIVOS")[1]

    for line in section.split("\n"):
        line = line.strip()

        nome_match = re.match(r'^([A-Za-z0-9\s\.\-]+?)\s+R\$', line)
        valor_match = re.search(r'R\$\s([\d\.,]+)', line)
        rent_match = re.search(r'R\$\s[\d\.,]+.*?([\-\+]?\d+,\d+)%', line)

        if not nome_match or not valor_match:
            continue

        nome = nome_match.group(1).strip()
        valor = parse_brl(valor_match.group(1))

        if valor <= 0:
            continue

        rent = parse_percent(rent_match.group(1)) if rent_match else None

        if any(x in nome.upper() for x in [
            "TOTAL","POSIÇÃO","ESTRATÉGIA","CAIXA","FUNDOS"
        ]):
            continue

        data.append({
            "ativo": nome,
            "valor": valor,
            "moeda": "BRL",
            "classe": classificar(nome,"BRL"),
            "rentabilidade": rent
        })

    return data

# ======================
# PARSER AVENUE (DEFINITIVO)
# ======================
def parse_avenue(text):
    data = []

    for line in text.split("\n"):
        line = line.strip()

        # ticker
        ticker_match = re.match(r'^([A-Z]{2,5})\b', line)
        if not ticker_match:
            continue

        ticker = ticker_match.group(1)

        # rentabilidade
        rent_match = re.search(r'([\+\-]?\d+,\d+)%', line)
        rent = parse_percent(rent_match.group(1)) if rent_match else None

        valor = None

        # 🔥 REGRA PRINCIPAL → número antes da %
        if rent_match:
            trecho = line[:rent_match.start()]
            numeros = re.findall(r'\d{1,3}(?:,\d{3})*\.\d{2}', trecho)

            if numeros:
                valor = parse_usd(numeros[-1])

        # 🔁 fallback (caso não tenha %)
        if valor is None:
            numeros = re.findall(r'\d{1,3}(?:,\d{3})*\.\d{2}', line)
            if numeros:
                valor = parse_usd(numeros[-1])

        if not valor or valor <= 0:
            continue

        data.append({
            "ativo": ticker,
            "valor": valor,
            "moeda": "USD",
            "classe": "Internacional",
            "rentabilidade": rent
        })

    return data

# ======================
# DETECTOR
# ======================
def detect_parser(text):
    t = text.upper()

    if "POSIÇÃO DETALHADA DOS ATIVOS" in t:
        return parse_xp(text)

    return parse_avenue(text)

# ======================
# ROTA
# ======================
@app.route('/upload', methods=['POST'])
def upload():
    try:
        files = request.files.getlist('files')
        carteira = []

        for f in files:
            with pdfplumber.open(f) as pdf:
                text = "".join([p.extract_text() or "" for p in pdf.pages])
                carteira.extend(detect_parser(text))

        return jsonify({
            "status": "ok",
            "ativos": carteira
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/')
def home():
    return "API OK 🚀"

if __name__ == "__main__":
    app.run(debug=True)
