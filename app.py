from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# =========================
# UTIL
# =========================

def limpar(texto):
    return re.sub(r"\s+", " ", texto.replace("\xa0", " ")).strip()

def extrair_valor(linha):
    m = re.search(r'(R\$|\$)\s?([\d\.,]+)', linha)
    if not m:
        return None

    valor = m.group(2).replace(".", "").replace(",", ".")
    try:
        return float(valor)
    except:
        return None

def extrair_rent(linha):
    m = re.search(r'(-?\d+[\.,]?\d*)%', linha)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))

def extrair_nome(linha):
    linha = re.sub(r'(R\$|\$)\s?[\d\.,]+', '', linha)
    linha = re.sub(r'-?\d+[\.,]?\d*%', '', linha)
    return " ".join(linha.split()[:3])

def detectar_moeda(linha):
    if "$" in linha:
        return "USD"
    return "BRL"

# =========================
# FILTRO (CRÍTICO)
# =========================
def linha_valida(linha):
    lixo = ["DATA", "MÊS", "MES", "ANO", "TOTAL", "SALDO"]
    linha_up = linha.upper()

    if any(x in linha_up for x in lixo):
        return False

    if not re.search(r"\d", linha):
        return False

    if len(linha.split()) < 2:
        return False

    return True

# =========================
# PROCESSAMENTO
# =========================
def processar_pdf(file):
    ativos = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            if not texto:
                continue

            for linha in texto.split("\n"):
                linha = limpar(linha)

                if not linha_valida(linha):
                    continue

                valor = extrair_valor(linha)
                if not valor:
                    continue

                ativos.append({
                    "ativo": extrair_nome(linha),
                    "valor": valor,
                    "moeda": detectar_moeda(linha),
                    "rentabilidade": extrair_rent(linha)
                })

    return ativos

# =========================
# ROTA
# =========================
@app.route("/upload", methods=["POST"])
def upload():
    print("FILES:", request.files)

    if "file" not in request.files:
        return jsonify({"erro": "Arquivo não enviado"}), 400

    file = request.files["file"]

    print("Arquivo:", file.filename)

    ativos = processar_pdf(file)

    print("Ativos:", ativos)

    return jsonify({"ativos": ativos})

@app.route("/")
def home():
    return "API OK"

# =========================
if __name__ == "__main__":
    app.run()
