```python
from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re

app = Flask(__name__)
CORS(app)  # permite requisições do seu site (WordPress)

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
# PARSER XP
# =========================
def parse_xp(text):
    data = []

    pattern = re.findall(
        r'([A-Za-z0-9\s\.\-]+)\sR\$\s([\d\.,]+).*?([\-\d\,]+%)',
        text
    )

    for match in pattern:
        data.append({
            "ativo": match[0].strip(),
            "valor": parse_brl(match[1]),
            "rentabilidade": parse_percent(match[2]),
            "moeda": "BRL",
            "fonte": "XP"
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
            "fonte": "Avenue"
        })

    return data

# =========================
# DETECÇÃO
# =========================
def detect_parser(text):
    if "XPerformance" in text or "XP" in text:
        return parse_xp(text)
    else:
        return parse_avenue(text)

# =========================
# ROTA PRINCIPAL
# =========================
@app.route('/upload', methods=['POST'])
def upload():
    try:
        files = request.files.getlist('files')

        if not files:
            return jsonify({"error": "Nenhum arquivo enviado"}), 400

        carteira = []

        for file in files:
            with pdfplumber.open(file) as pdf:
                text = ""

                for page in pdf.pages:
                    text += page.extract_text() or ""

                ativos = detect_parser(text)
                carteira.extend(ativos)

        return jsonify({
            "status": "ok",
            "total_ativos": len(carteira),
            "ativos": carteira
        })

    except Exception as e:
        return jsonify({
            "status": "erro",
            "mensagem": str(e)
        }), 500

# =========================
# ROTA TESTE
# =========================
@app.route('/')
def home():
    return "API de Consolidação de Carteira funcionando 🚀"

# =========================
# RUN LOCAL
# =========================
if __name__ == '__main__':
    app.run(debug=True)
```
