import os
from flask import Flask, render_template, request, jsonify
from compiler_logic import run_compiler

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/compile", methods=["POST"])
def compile_route():
    data = request.get_json(silent=True) or {}
    source = data.get("code", "")

    token_list, listing, icg, target, errors, symbol_table = run_compiler(source)

    return jsonify({
        "tokens": token_list,
        "listing": listing,
        "icg": icg,
        "target": target,
        "errors": errors,
        "symbol_table": symbol_table,
        "success": len(errors) == 0
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

