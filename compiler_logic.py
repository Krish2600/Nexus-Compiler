import re

KEYWORDS = {
    'program', 'var', 'begin', 'end', 'integer',
    'if', 'then', 'else', 'while', 'do',
    'read', 'write', 'array', 'of', 'function',
    'procedure', 'and', 'or', 'not'
}

SYMBOLS = {'(', ')', '[', ']', ';', ':', '.', ',', '*', '-', '+', '/', '<', '=', '>'}
COMPOUND = {':=', '<=', '>=', '<>'}


class Token:
    def __init__(self, type_, value, line):
        self.type = type_
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line})"


# =========================
# LEXER
# =========================
class Lexer:
    def __init__(self, text):
        self.lines = text.split('\n')

    def tokenize(self):
        tokens = []
        errors = []

        for ln, line in enumerate(self.lines, 1):
            # Strip inline comments
            if '!' in line:
                line = line[:line.index('!')]

            i = 0
            while i < len(line):
                ch = line[i]

                if ch.isspace():
                    i += 1
                    continue

                # Identifier or keyword
                if ch.isalpha() or ch == '_':
                    start = i
                    while i < len(line) and (line[i].isalnum() or line[i] == '_'):
                        i += 1
                    word = line[start:i]

                    # Identifier too long (> 32 chars)
                    if len(word) > 32:
                        errors.append(f"Line {ln}: Identifier '{word[:10]}...' exceeds 32 characters")
                        word = word[:32]

                    if word.lower() in KEYWORDS:
                        tokens.append(Token("KEYWORD", word.lower(), ln))
                    else:
                        tokens.append(Token("ID", word, ln))

                # Number
                elif ch.isdigit():
                    start = i
                    while i < len(line) and line[i].isdigit():
                        i += 1
                    # Check for invalid identifier starting with digit
                    if i < len(line) and line[i].isalpha():
                        errors.append(f"Line {ln}: Invalid token starting with digit")
                        while i < len(line) and (line[i].isalnum() or line[i] == '_'):
                            i += 1
                    else:
                        tokens.append(Token("NUMBER", line[start:i], ln))

                # String literal with escape handling
                elif ch == "'":
                    i += 1
                    string_val = ""
                    unclosed = True
                    while i < len(line):
                        c = line[i]
                        if c == '\\':
                            i += 1
                            if i < len(line):
                                esc = line[i]
                                if esc == 'n':
                                    string_val += '\n'
                                elif esc == 't':
                                    string_val += '\t'
                                else:
                                    string_val += esc
                                i += 1
                        elif c == "'":
                            unclosed = False
                            i += 1
                            break
                        else:
                            string_val += c
                            i += 1
                    if unclosed:
                        errors.append(f"Line {ln}: Unclosed string literal")
                    tokens.append(Token("STRING", string_val, ln))

                # Compound symbols (must check before single)
                elif i + 1 < len(line) and line[i:i+2] in COMPOUND:
                    tokens.append(Token("SYMBOL", line[i:i+2], ln))
                    i += 2

                elif ch in SYMBOLS:
                    tokens.append(Token("SYMBOL", ch, ln))
                    i += 1

                else:
                    errors.append(f"Line {ln}: Invalid character '{ch}'")
                    i += 1

        return tokens, errors


# =========================
# SYMBOL TABLE
# =========================
class SymbolTable:
    def __init__(self):
        self.table = {}

    def declare(self, name, type_):
        self.table[name.lower()] = type_

    def lookup(self, name):
        return self.table.get(name.lower())

    def entries(self):
        return list(self.table.items())


# =========================
# PARSER + ICG
# =========================
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.errors = []
        self.icg = []
        self.temp_count = 0
        self.label_count = 0
        self.symbol_table = SymbolTable()

    def new_temp(self):
        self.temp_count += 1
        return f"t{self.temp_count}"

    def new_label(self):
        self.label_count += 1
        return f"L{self.label_count}"

    def current(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def peek(self, offset=1):
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else None

    def eat(self, val=None, type_=None):
        tok = self.current()
        if tok is None:
            self.errors.append("Unexpected end of input")
            return None
        if val and tok.value != val:
            self.errors.append(f"Line {tok.line}: Expected '{val}' but got '{tok.value}'")
        if type_ and tok.type != type_:
            self.errors.append(f"Line {tok.line}: Expected {type_} but got {tok.type}")
        self.pos += 1
        return tok

    def parse(self):
        self.program()
        # Check for trailing tokens
        if self.current() is not None:
            tok = self.current()
            self.errors.append(f"Line {tok.line}: Unexpected token '{tok.value}' after program end")

    def program(self):
        self.eat("program")
        name_tok = self.current()
        self.eat()  # program name
        self.eat(";")

        if self.current() and self.current().value == "var":
            self.var_section()

        self.eat("begin")
        self.statement_list()
        self.eat("end")
        # Optional trailing dot
        if self.current() and self.current().value == ".":
            self.eat(".")

    def var_section(self):
        self.eat("var")
        while self.current() and self.current().type == "ID":
            names = []
            names.append(self.current().value)
            self.eat()
            while self.current() and self.current().value == ",":
                self.eat(",")
                names.append(self.current().value)
                self.eat()
            self.eat(":")
            # type: integer or array
            if self.current() and self.current().value == "array":
                self.eat("array")
                self.eat("[")
                size = self.current().value if self.current() else "?"
                self.eat()  # num
                self.eat("]")
                self.eat("of")
                self.eat("integer")
                for n in names:
                    self.symbol_table.declare(n, f"array[{size}] of integer")
            else:
                self.eat("integer")
                for n in names:
                    self.symbol_table.declare(n, "integer")
            self.eat(";")

    def statement_list(self):
        stop_values = {"end", "else"}
        while self.current() and self.current().value not in stop_values:
            self.statement()

    def statement(self):
        tok = self.current()
        if not tok:
            return

        if tok.value == "begin":
            self.compound_stmt()
        elif tok.value == "if":
            self.if_stmt()
        elif tok.value == "while":
            self.while_stmt()
        elif tok.value == "read":
            self.read_stmt()
        elif tok.value == "write":
            self.write_stmt()
        elif tok.type == "ID":
            self.assign_stmt()
        elif tok.value == ";":
            self.eat(";")  # empty statement
        else:
            self.errors.append(f"Line {tok.line}: Unexpected token '{tok.value}'")
            self.eat()

    def compound_stmt(self):
        self.eat("begin")
        self.statement_list()
        self.eat("end")
        if self.current() and self.current().value == ";":
            self.eat(";")

    def assign_stmt(self):
        var_tok = self.current()
        var = var_tok.value
        self.eat()

        # Array indexing: id[expr]
        if self.current() and self.current().value == "[":
            self.eat("[")
            idx = self.expression()
            self.eat("]")
            self.eat(":=")
            expr = self.expression()
            self.icg.append(f"{var}[{idx}] = {expr}")
        else:
            self.eat(":=")
            expr = self.expression()
            self.icg.append(f"{var} = {expr}")

        if self.current() and self.current().value == ";":
            self.eat(";")

    def read_stmt(self):
        self.eat("read")
        self.eat("(")
        while True:
            var = self.current().value if self.current() else "?"
            self.eat()
            self.icg.append(f"READ {var}")
            if not (self.current() and self.current().value == ","):
                break
            self.eat(",")
        self.eat(")")
        if self.current() and self.current().value == ";":
            self.eat(";")

    def write_stmt(self):
        self.eat("write")
        self.eat("(")
        while True:
            if self.current() and self.current().type == "STRING":
                val = f'"{self.current().value}"'
                self.eat()
            else:
                val = self.expression()
            self.icg.append(f"WRITE {val}")
            if not (self.current() and self.current().value == ","):
                break
            self.eat(",")
        self.eat(")")
        if self.current() and self.current().value == ";":
            self.eat(";")

    def if_stmt(self):
        self.eat("if")
        cond = self.expression()
        l_false = self.new_label()
        self.icg.append(f"IF NOT ({cond}) GOTO {l_false}")
        self.eat("then")
        self.statement()

        if self.current() and self.current().value == "else":
            l_end = self.new_label()
            self.icg.append(f"GOTO {l_end}")
            self.icg.append(f"{l_false}:")
            self.eat("else")
            self.statement()
            self.icg.append(f"{l_end}:")
        else:
            self.icg.append(f"{l_false}:")

    def while_stmt(self):
        self.eat("while")
        l_start = self.new_label()
        l_end = self.new_label()
        self.icg.append(f"{l_start}:")
        cond = self.expression()
        self.icg.append(f"IF NOT ({cond}) GOTO {l_end}")
        self.eat("do")
        self.statement()
        self.icg.append(f"GOTO {l_start}")
        self.icg.append(f"{l_end}:")

    def expression(self):
        # Handle 'not' unary
        if self.current() and self.current().value == "not":
            self.eat("not")
            operand = self.simple_expr()
            temp = self.new_temp()
            self.icg.append(f"{temp} = NOT {operand}")
            return temp

        left = self.simple_expr()

        rel_ops = {'<', '>', '=', '<>', '<=', '>='}
        if self.current() and self.current().value in rel_ops:
            op = self.current().value
            self.eat()
            right = self.simple_expr()
            temp = self.new_temp()
            self.icg.append(f"{temp} = {left} {op} {right}")
            return temp

        return left

    def simple_expr(self):
        left = self.term()
        while self.current() and self.current().value in ('+', '-', 'or'):
            op = self.current().value
            self.eat()
            right = self.term()
            temp = self.new_temp()
            self.icg.append(f"{temp} = {left} {op} {right}")
            left = temp
        return left

    def term(self):
        left = self.factor()
        while self.current() and self.current().value in ('*', '/', 'and'):
            op = self.current().value
            self.eat()
            right = self.factor()
            temp = self.new_temp()
            self.icg.append(f"{temp} = {left} {op} {right}")
            left = temp
        return left

    def factor(self):
        tok = self.current()
        if tok is None:
            self.errors.append("Unexpected end of input in expression")
            return "0"

        # Parenthesized expression
        if tok.value == "(":
            self.eat("(")
            val = self.expression()
            self.eat(")")
            return val

        # Unary minus
        if tok.value == "-":
            self.eat("-")
            operand = self.factor()
            temp = self.new_temp()
            self.icg.append(f"{temp} = -{operand}")
            return temp

        # Number
        if tok.type == "NUMBER":
            self.eat()
            return tok.value

        # ID or array access
        if tok.type == "ID":
            self.eat()
            if self.current() and self.current().value == "[":
                self.eat("[")
                idx = self.expression()
                self.eat("]")
                temp = self.new_temp()
                self.icg.append(f"{temp} = {tok.value}[{idx}]")
                return temp
            return tok.value

        self.errors.append(f"Line {tok.line}: Invalid factor '{tok.value}'")
        self.eat()
        return "0"


# =========================
# CODE GENERATOR (x86-like pseudo-assembly)
# =========================
class CodeGen:
    def __init__(self):
        self.reg_pool = ["EAX", "EBX", "ECX", "EDX"]
        self.used_regs = {}

    def generate(self, icg_lines):
        asm = ["; ===== Generated Assembly (pseudo x86) =====", "section .text", "global _start", "_start:"]
        for line in icg_lines:
            asm.append(f"    ; {line}")
            asm.append(self._translate(line))
        asm.append("    ; --- program exit ---")
        asm.append("    MOV EAX, 1")
        asm.append("    INT 0x80")
        return asm

    def _translate(self, line):
        line = line.strip()

        if line.endswith(":"):
            return f"{line}   ; label"

        if line.startswith("READ "):
            var = line[5:]
            return f"    ; syscall read -> [{var}]"

        if line.startswith("WRITE "):
            val = line[6:]
            return f"    ; syscall write <- {val}"

        if line.startswith("IF NOT"):
            # IF NOT (cond) GOTO label
            m = re.match(r"IF NOT \((.+)\) GOTO (\S+)", line)
            if m:
                cond, label = m.group(1), m.group(2)
                return f"    CMP {cond}, 0\n    JE {label}"

        if line.startswith("GOTO "):
            label = line[5:]
            return f"    JMP {label}"

        # Assignment: x = a op b  or  x = a
        m = re.match(r"(\S+)\s*=\s*(.+)", line)
        if m:
            dest, rhs = m.group(1), m.group(2).strip()
            # Binary op
            bop = re.match(r"(\S+)\s*([+\-*/]|and|or|[<>]=?|<>|=)\s*(\S+)", rhs)
            if bop:
                a, op, b = bop.group(1), bop.group(2), bop.group(3)
                op_map = {'+': 'ADD', '-': 'SUB', '*': 'IMUL', '/': 'IDIV',
                          'and': 'AND', 'or': 'OR', '<': 'SETL', '>': 'SETG',
                          '<=': 'SETLE', '>=': 'SETGE', '=': 'SETE', '<>': 'SETNE'}
                asm_op = op_map.get(op, f"OP_{op}")
                return f"    MOV EAX, {a}\n    {asm_op} EAX, {b}\n    MOV [{dest}], EAX"
            # Unary minus
            unm = re.match(r"-(\S+)", rhs)
            if unm:
                return f"    MOV EAX, {unm.group(1)}\n    NEG EAX\n    MOV [{dest}], EAX"
            # NOT
            if rhs.startswith("NOT "):
                operand = rhs[4:]
                return f"    MOV EAX, {operand}\n    NOT EAX\n    MOV [{dest}], EAX"
            # Simple copy
            return f"    MOV EAX, {rhs}\n    MOV [{dest}], EAX"

        return f"    ; (unhandled) {line}"


def create_listing(source, errors):
    lines = source.split('\n')
    out = []
    for i, line in enumerate(lines, 1):
        out.append(f"{i:4} | {line}")
        for e in errors:
            if f"Line {i}:" in e:
                out.append(f"       >> ERROR: {e}")
    return "\n".join(out)


def compile_code(source):
    lexer = Lexer(source)
    tokens, lex_errors = lexer.tokenize()

    parser = Parser(tokens)
    parser.parse()
    parse_errors = parser.errors

    all_errors = lex_errors + parse_errors
    listing = create_listing(source, all_errors)
    icg = parser.icg
    symbol_table = parser.symbol_table.entries()

    target = []
    if not all_errors:
        target = CodeGen().generate(icg)

    return tokens, listing, icg, target, all_errors, symbol_table


def run_compiler(source):
    tokens, listing, icg, target, errors, symbol_table = compile_code(source)
    token_list = [{"type": t.type, "value": t.value, "line": t.line} for t in tokens]
    return token_list, listing, icg, target, errors, symbol_table
