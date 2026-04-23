from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re

app = Flask(__name__)
CORS(app)

# =========================
# NORMALIZA RENTABILIDADE
# =========================
def normalizar_rent(rent):
    if rent is None:
        return None

    try:
        rent = float(rent)

        # Se vier como 3 (3%), vira 0.03
        if rent > 1:
            rent = rent / 100

        return rent
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
# PARSER GENÉRICO
# =========================
def extrair_ativos(texto):
    ativos = []

    linhas = texto.split("\n")

    for linha in linhas:
        # Remove espaços duplicados
        linha = re.sub(r'\s+', ' ', linha).strip()

        # =========================
        # PADRÃO USD (Avenue)
        # =========================
        match_usd = re.match(r'([A-Z]{2,5})\s+\$?([\d,\.]+)\s+USD\s+(-?[\d\.]+)%', linha)

        if match_usd:
            nome = match_usd.group(1)
            valor = float(match_usd.group(2).replace(",", ""))
            rent = normalizar_rent(match_usd.group(3))

            ativos.append({
                "ativo": nome,
                "valor": valor,
                "moeda": "USD",
                "classe": classificar(nome, "USD"),
                "rentabilidade": rent
            })
            continue

        # =========================
        # PADRÃO BRL (XP)
        # =========================
        match_brl = re.match(r'(.+?)\s+R\$ ?([\d\.,]+)\s+BRL\s+(-?[\d\.,]+)%', linha)

        if match_brl:
            nome = match_brl.group(1).strip()
            valor = float(match_brl.group(2).replace(".", "").replace(",", "."))
            rent = normalizar_rent(match_brl.group(3).replace(",", "."))

            ativos.append({
                "ativo": nome,
                "valor": valor,
                "moeda": "BRL",
                "classe": classificar(nome, "BRL"),
                "rentabilidade": rent
            })
            continue

    return ativos


# =========================
# ROTA
# =========================
@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")

    todos_ativos = []

    for file in files:
        with pdfplumber.open(file) as pdf:
            texto = ""
            for page in pdf.pages:
                texto += page.extract_text() + "\n"

            ativos = extrair_ativos(texto)
            todos_ativos.extend(ativos)

    return jsonify({
        "status": "ok",
        "ativos": todos_ativos
    })


# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(debug=True)
