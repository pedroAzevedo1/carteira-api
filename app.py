from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re

app = Flask(__name__)
CORS(app)

# =========================
# UTIL
# =========================

def limpar_texto(texto):
    if not texto:
        return ""
    texto = texto.replace("\xa0", " ")
    texto = re.sub(r"\s+", " ", texto)
    return texto.strip()


def is_linha_valida(linha):
    linha = linha.upper()

    # ignora lixo comum dos PDFs
    lixo = [
        "DATA", "MÊS", "MES", "ANO", "TOTAL", "SALDO",
        "POSIÇÃO", "POSICAO", "EXTRATO", "RENTABILIDADE",
        "VALORIZAÇÃO", "VALOR TOTAL"
    ]

    if any(l in linha for l in lixo):
        return False

    # precisa ter número (valor)
    if not re.search(r"\d", linha):
        return False

    # precisa ter pelo menos uma palavra (ativo)
    if len(linha.split()) < 2:
        return False

    return True


def extrair_valor(linha):
    # USD ou BRL
    match = re.search(r'(\$|R\$)\s?([\d.,]+)', linha)
    if match:
        valor = match.group(2).replace(".", "").replace(",", ".")
        try:
            return float(valor)
        except:
            return 0.0
    return 0.0


def extrair_moeda(linha):
    if "$" in linha:
        return "USD"
    if "R$" in linha:
        return "BRL"
    return "BRL"


def extrair_rentabilidade(linha):
    match = re.search(r'(-?\d+[.,]?\d*)%', linha)
    if match:
        val = match.group(1).replace(",", ".")
        try:
            return float(val)
        except:
            return 0.0
    return 0.0


def extrair_nome(linha):
    # remove valores e %
    linha = re.sub(r'(\$|R\$)\s?[\d.,]+', '', linha)
    linha = re.sub(r'-?\d+[.,]?\d*%', '', linha)

    partes = linha.split()

    # pega primeiras palavras como nome
    nome = " ".join(partes[:4])
    return nome.strip()


def classificar(nome):
    nome = nome.upper()

    if any(x in nome for x in ["TESOURO", "CDB", "LCI", "LCA", "RENDA FIXA"]):
        return "Renda Fixa"

    if any(x in nome for x in ["FII", "FUND", "ETF", "AÇÕES", "ACAO", "STOCK"]):
        return "Renda Variável"

    if any(x in nome for x in ["USD", "ETF", "TREASURY", "BOND"]):
        return "Internacional"

    return "Outros"


# =========================
# PROCESSAMENTO DO PDF
# =========================

def processar_pdf(file):
    ativos = []

    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()

            if not texto:
                continue

            linhas = texto.split("\n")

            for linha in linhas:
                linha = limpar_texto(linha)

                if not is_linha_valida(linha):
                    continue

                valor = extrair_valor(linha)
                if valor == 0:
                    continue

                nome = extrair_nome(linha)
                moeda = extrair_moeda(linha)
                rent = extrair_rentabilidade(linha)
                classe = classificar(nome)

                ativos.append({
                    "ativo": nome,
                    "valor": valor,
                    "moeda": moeda,
                    "rentabilidade": rent,
                    "classe": classe
                })

    return ativos


# =========================
# ROTAS
# =========================

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"erro": "Arquivo não enviado"}), 400

    file = request.files["file"]

    try:
        ativos = processar_pdf(file)

        if not ativos:
            return jsonify({
                "erro": "Nenhum ativo identificado. PDF pode estar em formato diferente."
            }), 400

        return jsonify({
            "ativos": ativos
        })

    except Exception as e:
        return jsonify({
            "erro": str(e)
        }), 500


@app.route("/")
def home():
    return "API Carteira OK 🚀"


