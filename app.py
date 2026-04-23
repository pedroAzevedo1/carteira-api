from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import fitz
import re

app = Flask(__name__)
CORS(app)

# =========================
def limpar(texto):
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r'\s+', ' ', texto)
    return texto

# =========================
def normalizar_rent(valor):
    try:
        v = float(str(valor).replace(",", "."))
        if v > 1:
            v /= 100
        return v
    except:
        return None

# =========================
def detectar_moeda(linha):
    if "$" in linha or "USD" in linha:
        return "USD"
    if "R$" in linha or "BRL" in linha:
        return "BRL"
    return None

# =========================
def extrair_valor(linha, moeda):
    try:
        if moeda == "USD":
            m = re.search(r'\$ ?([\d,\.]+)', linha)
            if m:
                return float(m.group(1).replace(",", ""))

        if moeda == "BRL":
            m = re.search(r'R\$ ?([\d\.\,]+)', linha)
            if m:
                return float(m.group(1).replace(".", "").replace(",", "."))
    except:
        return None
    return None

# =========================
def extrair_rent(linha):
    m = re.search(r'(-?[\d\.,]+)%', linha)
    if m:
        return normalizar_rent(m.group(1))
    return None

# =========================
def extrair_nome(linha):
    partes = linha.split()
    for p in partes:
        if any(c.isdigit() for c in p):
            continue
        if len(p) < 3:
            continue
        return p
    return partes[0]

# =========================
def classificar(ativo, moeda):
    if moeda == "USD":
        return "Internacional"
    if re.match(r'^[A-Z]{4}\d{1,2}$', ativo):
        return "Renda Variável"
    return "Renda Fixa"

# =========================
def extrair_ativos(texto):
    ativos = []
    linhas = texto.split("\n")

    for linha in linhas:
        linha = limpar(linha.strip())

        if len(linha) < 10:
            continue

        lixo = ["MÊS", "ANO", "TOTAL", "SALDO", "DATA"]
        if any(p in linha.upper() for p in lixo):
            continue

        moeda = detectar_moeda(linha)
        if not moeda:
            continue

        valor = extrair_valor(linha, moeda)
        if not valor or valor < 1:
            continue

        nome = extrair_nome(linha)

        if nome.upper() in ["R$", "USD", "BRL"]:
            continue

        if re.match(r'\w{3}/\d{2}', nome.lower()):
            continue

        rent = extrair_rent(linha)

        ativos.append({
            "ativo": nome,
            "valor": valor,
            "moeda": moeda,
            "classe": classificar(nome, moeda),
            "rentabilidade": rent
        })

    return ativos

# =========================
def ler_pdf(file):
    texto = ""

    try:
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    texto += t + "\n"
    except:
        pass

    if not texto:
        file.seek(0)
        doc = fitz.open(stream=file.read(), filetype="pdf")
        for page in doc:
            texto += page.get_text()

    return texto

# =========================
@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    todos = []

    for file in files:
        texto = ler_pdf(file)
        ativos = extrair_ativos(texto)
        todos.extend(ativos)

    return jsonify({
        "status": "ok",
        "ativos": todos
    })

# =========================
@app.route("/")
def home():
    return "API OK"

# =========================
if __name__ == "__main__":
    app.run(debug=True)
