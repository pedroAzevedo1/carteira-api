from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pdfplumber
import re
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table

app = Flask(__name__)
CORS(app)

# =========================
# FILTROS INTELIGENTES
# =========================

def linha_valida(nome):
    if not nome:
        return False

    nome = nome.strip().upper()

    # Ignorar lixo comum
    invalidos = [
        "DATA", "PERÍODO", "MES", "MÊS", "ANO",
        "TOTAL", "SALDO", "POSIÇÃO", "RENTABILIDADE",
        "EVOLUÇÃO", "VALOR", "R$", "USD"
    ]

    if any(x in nome for x in invalidos):
        return False

    # Ignorar datas tipo "jan/26"
    if re.match(r"^[A-Z]{3}/\d{2}$", nome):
        return False

    # Nome muito curto
    if len(nome) < 2:
        return False

    return True


def extrair_valor(texto):
    if not texto:
        return 0

    texto = texto.replace(".", "").replace(",", ".")

    nums = re.findall(r"\d+\.\d+", texto)
    return float(nums[0]) if nums else 0


def extrair_percentual(texto):
    if not texto:
        return 0

    match = re.search(r"-?\d+[\.,]?\d*%", texto)
    if match:
        return float(match.group().replace("%", "").replace(",", "."))
    return 0


# =========================
# LEITURA DE PDF
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
                partes = linha.split()

                if len(partes) < 3:
                    continue

                nome = " ".join(partes[:-2])
                valor_str = partes[-2]
                rent_str = partes[-1]

                if not linha_valida(nome):
                    continue

                valor = extrair_valor(valor_str)
                rent = extrair_percentual(rent_str)

                if valor == 0:
                    continue

                moeda = "USD" if "$" in linha else "BRL"

                ativos.append({
                    "nome": nome.strip(),
                    "valor": valor,
                    "rentabilidade": rent,
                    "moeda": moeda
                })

    return ativos


# =========================
# CONSOLIDAÇÃO
# =========================

def classificar(nome):
    nome = nome.upper()

    if any(x in nome for x in ["TESOURO", "CDB", "LCI", "LCA", "RF"]):
        return "Renda Fixa"

    if any(x in nome for x in ["FII", "IMOB", "JURO"]):
        return "FII"

    if any(x in nome for x in ["ETF", "SPY", "IVV", "QQQ"]):
        return "ETF"

    return "Ações"


def consolidar(ativos, cambio):
    total = 0
    total_ponderado = 0

    for a in ativos:
        valor = a["valor"]

        if a["moeda"] == "USD":
            valor *= cambio

        total += valor
        total_ponderado += valor * a["rentabilidade"]

    rent_total = (total_ponderado / total) if total > 0 else 0

    return total, rent_total


# =========================
# API
# =========================

@app.route("/processar", methods=["POST"])
def processar():
    files = request.files.getlist("files")
    cambio = float(request.form.get("cambio", 5.0))

    carteira = []

    for file in files:
        carteira.extend(processar_pdf(file))

    total, rent = consolidar(carteira, cambio)

    return jsonify({
        "ativos": carteira,
        "total": total,
        "rentabilidade": rent
    })


# =========================
# EXPORTAR PDF
# =========================

@app.route("/exportar", methods=["POST"])
def exportar():
    dados = request.json

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)

    tabela = [["Ativo", "Valor", "Rent (%)"]]

    for a in dados["ativos"]:
        tabela.append([
            a["nome"],
            f"{a['valor']:.2f}",
            f"{a['rentabilidade']:.2f}%"
        ])

    table = Table(tabela)
    doc.build([table])

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="carteira.pdf")


if __name__ == "__main__":
    app.run()


