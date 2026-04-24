from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re

app = Flask(__name__)
CORS(app)

# ===== PARSERS =====
def parse_brl(v):
    try: return float(v.replace('.', '').replace(',', '.'))
    except: return 0

def parse_usd(v):
    try: return float(v.replace(',', ''))
    except: return 0

def parse_percent(v):
    try: return float(v.replace(',', '.').replace('%',''))
    except: return None

# ===== CLASSIFICAÇÃO =====
def classificar(nome, moeda):
    nome = nome.upper()

    if moeda == "USD":
        return "Internacional"

    if re.match(r'^[A-Z]{4}\d{1,2}$', nome):
        return "Renda Variável"

    if "FII" in nome or "ETF" in nome:
        return "Renda Variável"

    return "Renda Fixa"

# ===== XP =====
def parse_xp(text):
    data = []

    if "POSIÇÃO DETALHADA DOS ATIVOS" not in text:
        return data

    section = text.split("POSIÇÃO DETALHADA DOS ATIVOS")[1]

    for line in section.split("\n"):
        ticker = re.search(r'\b[A-Z]{4}\d{1,2}\b', line)
        valor = re.search(r'R\$\s([\d\.,]+)', line)

        if not ticker or not valor:
            continue

        v = parse_brl(valor.group(1))
        if v <= 0:
            continue

        nome = ticker.group(0)

        data.append({
            "ativo": nome,
            "valor": v,
            "moeda": "BRL",
            "classe": classificar(nome,"BRL"),
            "rentabilidade": None
        })

    return data

# ===== AVENUE =====
def parse_avenue(text):
    data = []

    matches = re.findall(
        r'\b([A-Z]{2,5})\b.*?([\d,]+\.\d{2})\s+([\+\-]?\d+,\d+%)',
        text
    )

    for t, v, r in matches:
        valor = parse_usd(v)
        if valor <= 0:
            continue

        data.append({
            "ativo": t,
            "valor": valor,
            "moeda": "USD",
            "classe": "Internacional",
            "rentabilidade": parse_percent(r)
        })

    return data

# ===== DETECTOR =====
def detect_parser(text):
    t = text.upper()

    if "POSIÇÃO DETALHADA DOS ATIVOS" in t:
        return parse_xp(text)

    if re.search(r'\b[A-Z]{2,5}\b.*\d+,\d+%', text):
        return parse_avenue(text)

    return []

# ===== CONSOLIDA =====
def consolidar_ativos(lista):
    mapa = {}

    for item in lista:
        chave = f"{item['ativo']}_{item['moeda']}"

        if chave not in mapa:
            mapa[chave] = {
                **item,
                "somaRent": item["rentabilidade"] * item["valor"] if item["rentabilidade"] is not None else 0,
                "somaBase": item["valor"] if item["rentabilidade"] is not None else 0
            }
        else:
            mapa[chave]["valor"] += item["valor"]

            if item["rentabilidade"] is not None:
                mapa[chave]["somaRent"] += item["rentabilidade"] * item["valor"]
                mapa[chave]["somaBase"] += item["valor"]

    result = []

    for i in mapa.values():
        rent = i["somaRent"] / i["somaBase"] if i["somaBase"] > 0 else None

        result.append({
            "ativo": i["ativo"],
            "valor": i["valor"],
            "moeda": i["moeda"],
            "classe": i["classe"],
            "rentabilidade": rent
        })

    return result

# ===== ROUTE =====
@app.route('/upload', methods=['POST'])
def upload():
    try:
        files = request.files.getlist('files')
        carteira = []

        for file in files:
            with pdfplumber.open(file) as pdf:
                text = "".join([p.extract_text() or "" for p in pdf.pages])
                carteira.extend(detect_parser(text))

        ativos = consolidar_ativos(carteira)

        return jsonify({
            "status": "ok",
            "ativos": ativos
        })

    except Exception as e:
        return jsonify({"status":"erro","msg":str(e)}),500

@app.route('/')
def home():
    return "API OK 🚀"

if __name__ == "__main__":
    app.run(debug=True)

