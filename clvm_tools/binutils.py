import string

from clvm import KEYWORD_FROM_ATOM, KEYWORD_TO_ATOM, to_sexp_f
from clvm.casts import int_from_bytes, int_to_bytes

from ir.reader import read_ir
from ir.writer import write_ir
from ir.utils import (
    ir_as_symbol, ir_cons, ir_first, ir_listp, ir_null,
    ir_nullp, ir_rest, ir_symbol, ir_val, is_ir
)
from ir.Type import Type


def assemble_from_ir(ir_sexp):
    keyword = ir_as_symbol(ir_sexp)
    if keyword:
        if keyword[:1] == "#":
            keyword = keyword[1:]
        atom = KEYWORD_TO_ATOM.get(keyword)
        if atom:
            return to_sexp_f(atom)
        if True:
            return ir_val(ir_sexp)
        raise SyntaxError(
            "can't parse %s at %s" % (keyword, ir_sexp._offset))

    if not ir_listp(ir_sexp):
        return ir_val(ir_sexp)

    if ir_nullp(ir_sexp):
        return to_sexp_f([])

    # handle "q"
    first = ir_first(ir_sexp)
    keyword = ir_as_symbol(first)
    if keyword == "q":
        pass
        # TODO: note that any symbol is legal after this point

    sexp_1 = assemble_from_ir(first)
    sexp_2 = assemble_from_ir(ir_rest(ir_sexp))
    return sexp_1.cons(sexp_2)


def type_for_atom(atom):
    if len(atom) > 2:
        try:
            v = atom.decode("utf8")
            if all(c in string.printable for c in v):
                return Type.QUOTES
        except UnicodeDecodeError:
            pass
        return Type.HEX
    if int_to_bytes(int_from_bytes(atom)) == atom:
        return Type.INT
    return Type.HEX


def disassemble_to_ir(sexp, allow_keyword=None):
    if is_ir(sexp) and allow_keyword is not False:
        return ir_cons(ir_symbol("ir"), sexp)

    if sexp.nullp():
        return ir_null()

    if sexp.listp():
        if sexp.first().listp() or allow_keyword is None:
            allow_keyword = True
        v0 = disassemble_to_ir(sexp.first(), allow_keyword=allow_keyword)
        v1 = disassemble_to_ir(sexp.rest(), allow_keyword=False)
        return to_sexp_f((Type.CONS, (v0, v1)))

    as_atom = sexp.as_atom()
    if allow_keyword:
        v = KEYWORD_FROM_ATOM.get(as_atom)
        if v is not None and v != '.':
            return ir_symbol(v)

    return to_sexp_f((type_for_atom(as_atom), as_atom))


def disassemble(sexp):
    symbols = disassemble_to_ir(sexp)
    return write_ir(symbols)


def assemble(s):
    symbols = read_ir(s)
    return assemble_from_ir(symbols)
