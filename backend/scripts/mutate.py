"""Minimal mutation tester (mutmut does not run on native Windows).

    python -m scripts.mutate app/services/scoring/engine.py tests/test_engine.py tests/test_engine_properties.py

Each mutant changes one thing in the target file (comparison, arithmetic or boolean operator, a constant, a negation);
the given tests are run against it with --noconftest. A "survived" mutant is a change no test noticed.
"""
import ast
import copy
import subprocess
import sys
from pathlib import Path

CMP_SWAP = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
            ast.Is: ast.IsNot, ast.IsNot: ast.Is, ast.In: ast.NotIn, ast.NotIn: ast.In}
BIN_SWAP = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult}
BOOL_SWAP = {ast.And: ast.Or, ast.Or: ast.And}


def mutants(tree: ast.Module):
    """Yield (description, mutated tree) for every single-point mutation."""
    nodes = [n for n in ast.walk(tree) if hasattr(n, "lineno")]
    for idx, node in enumerate(nodes):
        def mutate(fn, desc, idx=idx):
            t = copy.deepcopy(tree)
            target = [n for n in ast.walk(t) if hasattr(n, "lineno")][idx]
            if fn(target):
                return desc, t
            return None

        cands = []
        if isinstance(node, ast.Compare):
            for i, op in enumerate(node.ops):
                if type(op) in CMP_SWAP:
                    cands.append(mutate(lambda n, i=i: n.ops.__setitem__(i, CMP_SWAP[type(n.ops[i])]()) or True,
                                        f"line {node.lineno}: {type(op).__name__} -> {CMP_SWAP[type(op)].__name__}"))
        elif isinstance(node, ast.BinOp) and type(node.op) in BIN_SWAP:
            cands.append(mutate(lambda n: setattr(n, "op", BIN_SWAP[type(n.op)]()) or True,
                                f"line {node.lineno}: {type(node.op).__name__} -> {BIN_SWAP[type(node.op)].__name__}"))
        elif isinstance(node, ast.BoolOp):
            cands.append(mutate(lambda n: setattr(n, "op", BOOL_SWAP[type(n.op)]()) or True,
                                f"line {node.lineno}: {type(node.op).__name__} -> {BOOL_SWAP[type(node.op)].__name__}"))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            cands.append(mutate(lambda n: setattr(n, "op", ast.UAdd()) or True, f"line {node.lineno}: drop `not`"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            cands.append(mutate(lambda n: setattr(n, "value", not n.value) or True, f"line {node.lineno}: flip {node.value}"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, int | float) and not isinstance(node.value, bool):
            cands.append(mutate(lambda n: setattr(n, "value", n.value + 1) or True,
                                f"line {node.lineno}: constant {node.value} -> {node.value + 1}"))
        yield from (c for c in cands if c)


def main(argv: list[str]) -> int:
    target, tests = Path(argv[0]), argv[1:]
    original = target.read_text(encoding="utf-8")
    tree = ast.parse(original)
    survived, killed = [], 0
    try:
        for desc, mutant in mutants(tree):
            target.write_text(ast.unparse(mutant), encoding="utf-8")
            r = subprocess.run([sys.executable, "-m", "pytest", "-x", "-q", "--noconftest", "-p", "no:cacheprovider",
                                *tests], capture_output=True, text=True)
            if r.returncode == 0:
                survived.append(desc)
                print(f"SURVIVED  {desc}", flush=True)
            else:
                killed += 1
                print(f"killed    {desc}", flush=True)
    finally:
        target.write_text(original, encoding="utf-8")
    total = killed + len(survived)
    print(f"\n{killed}/{total} mutants killed ({100 * killed / max(total, 1):.0f}%), {len(survived)} survived")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
