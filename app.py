from flask import Flask, render_template, request
import sqlite3
import json
from escpos.printer import Usb  # Para impressora USB; use Network() se for rede
from datetime import datetime

app = Flask(__name__)

# Conectar ao banco de dados SQLite
conn = sqlite3.connect('pedidos.db', check_same_thread=False)
c = conn.cursor()

# Criar tabela de pedidos se não existir (agora com hora)
c.execute('''
CREATE TABLE IF NOT EXISTS pedidos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    telefone TEXT,
    itens TEXT,
    status TEXT,
    hora TEXT
)
''')
conn.commit()

# Carrega itens disponíveis do dia
with open("items.json") as f:
    itens_disponiveis = json.load(f)

# --- ROTAS --- #

# Página do cliente: reserva
@app.route("/", methods=["GET", "POST"])
def reservar():
    if request.method == "POST":
        nome = request.form["nome"]
        telefone = request.form["telefone"]
        itens = []
        for item in itens_disponiveis:
            q = request.form.get(f"quantidade_{item['nome']}")
            if q and int(q) > 0:
                itens.append({"nome": item["nome"], "quantidade": int(q)})
        if not itens:
            return "<h3>Selecione pelo menos um item!</h3>"

        hora_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO pedidos (nome, telefone, itens, status, hora) VALUES (?, ?, ?, ?, ?)",
                  (nome, telefone, json.dumps(itens), "reservado", hora_atual))
        conn.commit()
        return "<h3>Reserva efetuada! Compareça ao estabelecimento para pagamento.</h3>"

    return render_template("reserva.html", itens=itens_disponiveis)

# Página administrativa: listar pedidos do dia
@app.route("/admin", methods=["GET", "POST"])
def admin():
    pedidos = []
    if request.method == "POST":
        hoje = datetime.now().strftime("%Y-%m-%d")
        c.execute("SELECT * FROM pedidos WHERE hora LIKE ?", (hoje + "%",))
        pedidos = c.fetchall()
        # Converter itens JSON para lista Python
        for i in range(len(pedidos)):
            pedidos[i] = list(pedidos[i])
            pedidos[i][3] = json.loads(pedidos[i][3])
    return render_template("admin.html", pedidos=pedidos)

# Emitir cupom PDV (impressora térmica)
@app.route("/imprimir/<int:pedido_id>")
def imprimir(pedido_id):
    c.execute("SELECT * FROM pedidos WHERE id=?", (pedido_id,))
    pedido = c.fetchone()
    if not pedido:
        return "Pedido não encontrado"

    itens = json.loads(pedido[3])

    # Conectar à impressora térmica USB
    # Ajuste os IDs VendorID e ProductID da sua impressora
    p = Usb(0x04b8, 0x0e15)  # exemplo Epson, substitua pelos seus IDs

    # Montar cupom
    p.text("=== CUPOM PEDIDO ===\n")
    p.text(f"Cliente: {pedido[1]}\n")
    p.text(f"Telefone: {pedido[2]}\n")
    p.text(f"Hora: {pedido[5]}\n")
    p.text("-------------------\n")
    for item in itens:
        p.text(f"{item['nome']} x {item['quantidade']}\n")
    p.text("-------------------\n")
    p.text("Status: PAGO\n")
    p.text("\nObrigado!\n")
    p.cut()

    # Atualizar status
    c.execute("UPDATE pedidos SET status='pago' WHERE id=?", (pedido_id,))
    conn.commit()

    return "Cupom PDV impresso com sucesso!"

# --- EXECUÇÃO --- #
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
