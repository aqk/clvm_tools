import binascii

from clvm import to_sexp_f

from clvm.make_eval import EvalError

from ir.utils import (
    ir_nullp, ir_as_sexp, ir_is_atom, ir_listp,
    ir_first, ir_rest, ir_as_symbol, ir_iter,
    is_ir
)

from opacity import binutils


class bytes_as_hex(bytes):
    def as_hex(self):
        return binascii.hexlify(self).decode("utf8")

    def __str__(self):
        return "0x%s" % self.as_hex()

    def __repr__(self):
        return "0x%s" % self.as_hex()


def static_eval(sexp):
    # TODO: improve, and do deep eval if possible
    operator = sexp.first()
    if not operator.listp():
        if not operator.nullp():
            as_atom = operator.as_atom()
            if as_atom == "quote":
                return sexp.rest().first()
    raise EvalError("non static value", sexp)


def check_arg_count(args, count):
    actual_count = len(args.as_python())
    if actual_count != count:
        raise SyntaxError("bad argument count %d instead of %d" % (actual_count, count))


def make_compile_remap(compiled_keyword):
    def do_compile(args):
        return binutils.assemble(compiled_keyword).cons(args)
    return do_compile


def quote_arg(arg):
    return to_sexp_f([binutils.assemble("q"), arg])


def make_simple_replacement(src_opcode, obj_opcode=None):
    if obj_opcode is None:
        obj_opcode = src_opcode
    return [src_opcode.encode("utf8"), binutils.assemble("(c (q #%s) (a))" % obj_opcode)]


DEFAULT_REWRITE_RULES = to_sexp_f([
    make_simple_replacement("+"),
    make_simple_replacement("-"),
    make_simple_replacement("*"),
    make_simple_replacement("cons", "c"),
    make_simple_replacement("first", "f"),
    make_simple_replacement("rest", "r"),
    make_simple_replacement("args", "a"),
    make_simple_replacement("equal", "="),
    make_simple_replacement("eval", "e"),
    make_simple_replacement("if_op", "i"),
    make_simple_replacement("="),
    make_simple_replacement("sha256"),
    make_simple_replacement("wrap"),
    [b"test", binutils.assemble("(q (30 (+ (q 100) (q 10))))")],
    [b"compile_op", binutils.assemble("(c (q 32) (c (f (a)) (q ())))")],
    [b"list", binutils.assemble("(33 (a))")],
    [b"if", binutils.assemble("(34 (a))")],
    [b"ir_cons", binutils.assemble("(35 (a))")],
    [b"ir_int", binutils.assemble("(c (q #c) (c (c (q #q) (c (q 22) (q ()))) (c (f (a)) (q ()))))")],
    [b"ir_hex", binutils.assemble("(c (q #c) (c (c (q #q) (c (q 23) (q ()))) (c (f (a)) (q ()))))")],
    [b"ir_quotes", binutils.assemble("(c (q #c) (c (c (q #q) (c (q 24) (q ()))) (c (f (a)) (q ()))))")],
    [b"ir_symbol", binutils.assemble("(c (q #c) (c (c (q #q) (c (q 25) (q ()))) (c (f (a)) (q ()))))")],
    [b"ir_list", binutils.assemble("(36 (a))")],
])


def quoted(arg):
    return to_sexp_f([binutils.assemble("#q"), arg])


def do_compile_list(args, eval_f):
    args = args.first()
    if args.nullp():
        return binutils.assemble("(q ())")
    first = args.first()
    rest = do_compile_list(to_sexp_f([args.rest()]), eval_f)
    return to_sexp_f([binutils.assemble("#c"), first, rest])


def do_compile_ir_cons(args, eval_f):
    args = args.first()
    # (ir_cons A B) where A B are programs
    #   => (c 21 (c A B))
    prog_a = args.first()
    prog_b = args.rest().first()
    return to_sexp_f([binutils.assemble("c"), binutils.assemble("(q 21)"), 
        [binutils.assemble("c"), prog_a, prog_b]])


def do_compile_ir_list(args, eval_f):
    args = args.first()
    # (ir_cons A B) where A B are programs
    #   => (c 21 (c A B))
    if args.nullp():
        return binutils.assemble("(q ())")
    first = args.first()
    rest = do_compile_list(to_sexp_f([args.rest()]), eval_f)
    return to_sexp_f([binutils.assemble("#c"), first, rest])


def do_compile_if(args, eval_f):
    args = args.first()
    # (if A B C) where A B C are programs
    #   => (e (i A B C) (a))
    prog_a = args.first()
    prog_b = quoted(args.rest().first())
    prog_c = quoted(args.rest().rest().first())
    return to_sexp_f([binutils.assemble("e"), [binutils.assemble("i"), prog_a, prog_b, prog_c], binutils.assemble("(a)")])


def inner_op_compile_op(args, eval_f):
    if len(args.as_python()) not in (1, 2):
        raise SyntaxError("compile_op needs 1 or 2 arguments")

    if args.rest().nullp():
        rewrite_rules = DEFAULT_REWRITE_RULES
    else:
        rewrite_rules = args.rest().first()

    ir_sexp = args.first()
    if not is_ir(ir_sexp):
        raise SyntaxError("trying to compile %s which is not an ir_sexp" % ir_sexp)

    if ir_nullp(ir_sexp):
        return binutils.assemble("(q ())")

    if ir_is_atom(ir_sexp):
        return quoted(ir_as_sexp(ir_sexp))

    operator = ir_as_symbol(ir_first(ir_sexp))
    if operator is None:
        raise ValueError("symbol expected")

    # handle "quote" special
    if operator == "quote":
        ir_sexp = ir_rest(ir_sexp)
        return binutils.assemble("#q").cons(ir_sexp)

    compiled_args = []
    for _ in ir_iter(ir_rest(ir_sexp)):
        subexp = to_sexp_f([_, rewrite_rules])
        r = op_compile_op(subexp, eval_f)
        compiled_args.append(r)
    new_args = to_sexp_f(compiled_args)

    for pair in rewrite_rules.as_iter():
        if operator == pair.first().as_atom().decode("utf8"):
            code = pair.rest().first()
            from opacity.binutils import disassemble
            print("%s [%s]" % (disassemble(code), disassemble(new_args)))
            r = eval_f(eval_f, code, new_args)
            print("%s [%s] => %s" % (disassemble(code), disassemble(new_args), disassemble(r)))
            return r

    raise ValueError("can't compile %s" % operator)


def op_compile_op(args, eval_f):
    from ir import writer
    ir_sexp = args.first()
    print("about to compile %s" % writer.write_ir(ir_sexp))

    r = inner_op_compile_op(args, eval_f)
    from opacity.binutils import disassemble
    print("compiled %s => %s" % (writer.write_ir(ir_sexp), disassemble(r)))
    return r


"""
Copyright 2019 Chia Network Inc

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
