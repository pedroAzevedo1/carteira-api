from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re

app = Flask(__name__)
CORS(app)

# =========================
# NORMALIZA RENTABILIDADE
# =========================
def normalizar_rent(valor):
    try:
        valor = float(str(valor).replace(",", "."))

        # Se vier como 3 (3%), vira 0.03
        if valor > 1:
            valor = valor / 100

        return valor
    except:
        return None


# =========================
# CLASSIFICAÇÃO
# =========================
def classificar(ativo, moeda):
    ativo = ativo.upper()

    if moeda == "USD":
        return "Internacional"

    if re.match(r'^[A-Z]{4}\d{1,2}$', ativo):
        return "Renda Variável"

    if "FII" in ativo or "ETF" in ativo:
        return "Renda Variável"

    return "Renda Fixa"


# =========================
# LIMPA TEXTO
# =========================
def limpar_linha(linha):
    linha = linha.replace("\xa0", " ")
    linha = re.sub(r'\s+', ' ', linha)
    return linha.strip()


# =========================
# EXTRAI VALOR
# =========================
def extrair_valor(linha, moeda):
    try:
        if moeda == "USD":
            match = re.search(r'\$ ?([\d,\.]+)', linha)
            if match:
                return float(match.group(1).replace(",", ""))

        if moeda == "BRL":
            match = re.search(r'R\$ ?([\d\.\,]+)', linha)
            if match:
                return float(match.group(1).replace(".", "").replace(",", "."))

    except:
        return None

    return None


# =========================
# EXTRAI RENTABILIDADE
# =========================
def extrair_rent(linha):
    match = re.search(r'(-?[\d\.,]+)%', linha)

    if match:
        return normalizar_rent(match.group(1))

    return None


# =========================
# DETECTA MOEDA
# =========================
def detectar_moeda(linha):
    if "USD" in linha or "$" in linha:
        return "USD"
    if "R$" in linha or "BRL" in linha:
        return "BRL"
    return None


# =========================
# EXTRAI NOME DO ATIVO
# =========================
def extrair_nome(linha):
    partes = linha.split(" ")

    for p in partes:
        if len(p) > 2 and not any(c.isdigit() for c in p[:1]):
            return p

    return partes[0]


# =========================
# PARSER PRINCIPAL
# =========================
def extrair_ativos(texto):
    ativos = []

    linhas = texto.split("\n")

    for linha in linhas:
        linha = limpar_linha(linha)

        if len(linha) < 8:
            continue

        moeda = detectar_moeda(linha)
        if not moeda:
            continue

        valor = extrair_valor(linha, moeda)
        if not valor:
            continue

        nome = extrair_nome(linha)
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
# LEITURA PDF (ROBUSTA)
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
        return ""

    return texto


# =========================
# ROTA PRINCIPAL
# =========================
@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")

    todos_ativos = []

    for file in files:
        texto = ler_pdf(file)

        if not texto:
            continue

        ativos = extrair_ativos(texto)
        todos_ativos.extend(ativos)

    return jsonify({
        "status": "ok",
        "total_ativos": len(todos_ativos),
        "ativos": todos_ativos
    })


# =========================
# HEALTH CHECK
# =========================
@app.route("/")
def home():
    return "API OK"


# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(debug=True) 
