```python
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
def classificar(nome, moeda):
    nome = nome.upper()

    if moeda == "USD":
        return "Internacional"

    if re.match(r'^[A-Z]{4}\d{1,2}$', nome):
        return "Renda Variável"

    if "FII" in nome or "ETF" in nome or "FUNDO" in nome:
        return "Renda Variável"

    return "Renda Fixa"

# =========================
# PARSER XP (CORRIGIDO)
# =========================
def parse_xp(text):
    data = []

    if "POSIÇÃO DETALHADA DOS ATIVOS" not in text:
        return data

    section = text.split("POSIÇÃO DETALHADA DOS ATIVOS")[1]
    lines = section.split("\n")

    for line in lines:
        match = re.search(r'(.+?)\sR\$\s([\d\.,]+)', line)

        if not match:
            continue

        nome = match.group(1).strip()
        valor = parse_brl(match.group(2))
        nome_upper = nome.upper()

        # 🚫 FILTRO DE LIXO
        if (
            len(nome) < 4
            or any(x in nome_upper for x in [
                "TOTAL", "VALOR", "POSIÇÃO", "LISTADOS",
                "RENDA FIXA", "RENDA VARIÁVEL", "PÓS",
                "TESOURO", "APLICAÇÃO", "SALDO"
            ])
        ):
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
        data.append({
            "ativo": match[0],
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
def consolidar_ativos(lista):
    mapa = {}

    for item in lista:
        chave = item["ativo"]

        if chave not in mapa:
            mapa[chave] = {
                **item,
                "somaRent": (item["rentabilidade"] or 0) * item["valor"],
                "valorTotal": item["valor"]
            }
        else:
            mapa[chave]["valor"] += item["valor"]
            mapa[chave]["somaRent"] += (item["rentabilidade"] or 0) * item["valor"]
            mapa[chave]["valorTotal"] += item["valor"]

    resultado = []

    for item in mapa.values():
        rent = None
        if item["valorTotal"] > 0 and item["somaRent"] > 0:
            rent = item["somaRent"] / item["valorTotal"]

        resultado.append({
            "ativo": item["ativo"],
            "valor": item["valor"],
            "moeda": item["moeda"],
            "classe": item["classe"],
            "rentabilidade": rent
        })

    return resultado

# =========================
# CONSOLIDA CLASSES
# =========================
def consolidar_classes(lista):
    classes = {}

    for item in lista:
        c = item["classe"]
        classes[c] = classes.get(c, 0) + item["valor"]

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

if __name__ == "__main__":
    app.run(debug=True)
```

