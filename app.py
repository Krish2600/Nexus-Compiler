from flask import Flask, render_template, request, jsonify
from compiler_logic import run_compiler

app = Flask(__name__)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/compile", methods=["POST"])
def compile_route():
    data = request.get_json()
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
    app.run(debug=True, use_reloader=False)
