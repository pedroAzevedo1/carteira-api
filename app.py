from flask import Flask, request, jsonify
from flask_cors import CORS
import pdfplumber
import re

app = Flask(__name__)
CORS(app)

def parse_brl(v):
    try: return float(v.replace('.', '').replace(',', '.'))
    except: return 0

def parse_percent(v):
    try: return float(v.replace(',', '.').replace('%',''))
    except: return None

def classificar(nome, moeda):
    nome = nome.upper()

    if moeda == "USD":
        return "Internacional"

    if re.match(r'^[A-Z]{4}\d{1,2}$', nome):
        return "Renda Variável"

    if "FII" in nome or "ETF" in nome:
        return "Renda Variável"

    return "Renda Fixa"

# ===== PARSER XP (CORRIGIDO DE VERDADE) =====
def parse_xp(text):
    data = []

    if "POSIÇÃO DETALHADA DOS ATIVOS" not in text:
        return data

    section = text.split("POSIÇÃO DETALHADA DOS ATIVOS")[1]
    lines = section.split("\n")

    for line in lines:
        line = line.strip()

        nome_match = re.match(r'^([A-Za-z0-9\s\.\-]+?)\s+R\$', line)
        valor_match = re.search(r'R\$\s([\d\.,]+)', line)
        rent_match = re.search(r'R\$\s[\d\.,]+.*?([\-\+]?\d+,\d+)%', line)

        if not nome_match or not valor_match:
            continue

        nome = nome_match.group(1).strip()
        valor = parse_brl(valor_match.group(1))

        if valor <= 0:
            continue

        rent = parse_percent(rent_match.group(1)) if rent_match else None

        nome_upper = nome.upper()
        if any(x in nome_upper for x in [
            "TOTAL","POSIÇÃO","ESTRATÉGIA",
            "PÓS FIXADO","FUNDOS LISTADOS","CAIXA"
        ]):
            continue

        data.append({
            "ativo": nome,
            "valor": valor,
            "moeda": "BRL",
            "classe": classificar(nome,"BRL"),
            "rentabilidade": rent
        })

    return data

# ===== CONSOLIDA =====
def consolidar(lista):
    mapa = {}

    for i in lista:
        chave = f"{i['ativo']}_{i['moeda']}"

        if chave not in mapa:
            mapa[chave] = {
                **i,
                "somaRent": i["rentabilidade"]*i["valor"] if i["rentabilidade"] is not None else 0,
                "somaBase": i["valor"] if i["rentabilidade"] is not None else 0
            }
        else:
            mapa[chave]["valor"] += i["valor"]

            if i["rentabilidade"] is not None:
                mapa[chave]["somaRent"] += i["rentabilidade"]*i["valor"]
                mapa[chave]["somaBase"] += i["valor"]

    result = []

    for i in mapa.values():
        rent = i["somaRent"]/i["somaBase"] if i["somaBase"]>0 else None

        result.append({
            "ativo": i["ativo"],
            "valor": i["valor"],
            "moeda": i["moeda"],
            "classe": i["classe"],
            "rentabilidade": rent
        })

    return result

@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    carteira = []

    for f in files:
        with pdfplumber.open(f) as pdf:
            text = "".join([p.extract_text() or "" for p in pdf.pages])
            carteira.extend(parse_xp(text))

    ativos = consolidar(carteira)

    return jsonify({"ativos": ativos})

if __name__ == "__main__":
    app.run(debug=True)
