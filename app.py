from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re

app = Flask(__name__)
CORS(app)

# =========================
# UTIL
# =========================
def parse_brl(value):
    try:
        return float(value.replace('.', '').replace(',', '.'))
    except:
        return 0

def parse_usd(value):
    try:
        return float(value.replace(',', ''))
    except:
        return 0

def parse_percent(value):
    try:
        return float(value.replace(',', '.').replace('%', ''))
    except:
        return None

# =========================
# CLASSIFICAÇÃO
# =========================
def classificar(ativo, moeda):
    nome = ativo.upper()

    if moeda == "USD":
        return "Internacional"

    if any(x in nome for x in ["FII", "FUNDO", "ETF"]):
        return "Renda Variável"

    if re.match(r'^[A-Z]{4}\d{1,2}$', nome):  # tipo PETR4
        return "Renda Variável"

    return "Renda Fixa"

# =========================
# PARSER XP
# =========================
def parse_xp(text):
    data = []

    if "POSIÇÃO DETALHADA DOS ATIVOS" not in text:
        return data

    section = text.split("POSIÇÃO DETALHADA DOS ATIVOS")[1]
    lines = section.split("\n")

    for line in lines:
        match = re.search(r'(.+?)\sR\$\s([\d\.,]+)', line)

        if match:
            nome = match.group(1).strip()
            valor = parse_brl(match.group(2))

            if len(nome) < 3:
                continue

            data.append({
                "ativo": nome,
                "valor": valor,
                "rentabilidade": None,
                "moeda": "BRL",
                "classe": classificar(nome, "BRL")
            })

    return data

# =========================
# PARSER AVENUE
# =========================
def parse_avenue(text):
    data = []

    pattern = re.findall(
        r'([A-Z]{2,5})\s.*?\s([\d\.,]+)\s([\+\-]?\d+,\d+%)',
        text
    )

    for match in pattern:
        ativo = match[0]

        data.append({
            "ativo": ativo,
            "valor": parse_usd(match[1]),
            "rentabilidade": parse_percent(match[2]),
            "moeda": "USD",
            "classe": "Internacional"
        })

    return data

# =========================
# DETECTOR
# =========================
def detect_parser(text):
    if "XP" in text or "XPerformance" in text:
        return parse_xp(text)
    return parse_avenue(text)

# =========================
# CONSOLIDA ATIVOS
# =========================
def consolidar_ativos(carteira):
    consolidado = {}

    for item in carteira:
        chave = item["ativo"]

        if chave not in consolidado:
            consolidado[chave] = item.copy()
        else:
            consolidado[chave]["valor"] += item["valor"]

    return list(consolidado.values())

# =========================
# CONSOLIDA CLASSES
# =========================
def consolidar_classes(carteira):
    classes = {}

    for item in carteira:
        classe = item["classe"]

        if classe not in classes:
            classes[classe] = 0

        classes[classe] += item["valor"]

    return [{"classe": k, "valor": v} for k, v in classes.items()]

# =========================
# ROTA
# =========================
@app.route('/upload', methods=['POST'])
def upload():
    try:
        files = request.files.getlist('files')

        carteira = []

        for file in files:
            with pdfplumber.open(file) as pdf:
                text = ""

                for page in pdf.pages:
                    text += page.extract_text() or ""

                carteira.extend(detect_parser(text))

        ativos = consolidar_ativos(carteira)
        classes = consolidar_classes(ativos)

        return jsonify({
            "status": "ok",
            "ativos": ativos,
            "classes": classes
        })

    except Exception as e:
        return jsonify({
            "status": "erro",
            "mensagem": str(e)
        }), 500

@app.route('/')
def home():
    return "API rodando 🚀"

if __name__ == '__main__':
    app.run(debug=True)
