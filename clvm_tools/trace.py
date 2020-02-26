import argparse
import importlib
import io
import sys

from clvm import to_sexp_f
from clvm.EvalError import EvalError
from clvm.serialize import sexp_to_stream

from ir import reader

from . import binutils, patch_sexp  # noqa

from .cmds import path_or_code, stream_to_bin, stage_import


def trace_to_text(trace, disassemble, symbol_table):
    from clvm.more_ops import op_sha256tree
    for item in trace:
        form, env, cost_before, cost_after, rv = item
        h = op_sha256tree(form.to([form])).as_atom().hex()
        display_sexp = env.to(symbol_table[h].encode()).cons(env)
        print("%s => %s" % (disassemble(display_sexp), disassemble(rv)))
        print("")


def make_trace_pre_and_post_eval(log_entries, symbol_table):

    from clvm.more_ops import op_sha256tree

    def pre_eval_f(sexp, args, current_cost, max_cost):
        h = op_sha256tree(sexp.to([sexp])).as_atom().hex()
        if h in symbol_table:
            log_entry = [sexp, args.rest(), current_cost, None, None]
            log_entries.append(log_entry)
            return log_entry

    def post_eval_f(context, r):
        if context:
            log_entry = context
            log_entry[-2:] = r

    return pre_eval_f, post_eval_f


def clvmt():
    return launch_tool(sys.argv, "run", default_stage=2)


def launch_tool(args, tool_name, default_stage=0):
    parser = argparse.ArgumentParser(
        description='Execute a clvm script.'
    )
    parser.add_argument(
        "-s", "--stage", type=stage_import,
        help="stage number to include", default=stage_import(default_stage))
    parser.add_argument(
        "path_or_code", type=path_or_code,
        help="path to clvm script, or literal script")
    parser.add_argument(
        "args", type=reader.read_ir, help="arguments", nargs="?",
        default=reader.read_ir("()"))

    args = parser.parse_args(args=args[1:])

    run_program = args.stage.run_program

    src_text = args.path_or_code
    src_sexp = reader.read_ir(src_text)
    assembled_sexp = binutils.assemble_from_ir(src_sexp)

    pre_eval_f, post_eval_f = None, None

    import json
    with open("main.SYM") as f:
        symbol_table = json.load(f)

    log_entries = []
    pre_eval_f, post_eval_f = make_trace_pre_and_post_eval(log_entries, symbol_table)

    run_script = getattr(args.stage, tool_name)

    cost = 0
    try:
        env = binutils.assemble_from_ir(args.args)
        input_sexp = to_sexp_f((assembled_sexp, env))
        cost, result = run_program(
            run_script, input_sexp, pre_eval_f=pre_eval_f, post_eval_f=post_eval_f)
    except EvalError:
        return -1
    finally:
        trace_to_text(log_entries, binutils.disassemble, symbol_table)


"""
Copyright 2018 Chia Network Inc

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
