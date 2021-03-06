from functools import wraps
from textwrap import dedent
from gurklang.vm import run, run_with_middleware
from gurklang.parser import parse
from gurklang.types import Instruction, Int, Stack, Str, Vec
from gurklang.vm_utils import stringify_stack, render_value_as_source

from hypothesis import given, infer
from hypothesis.strategies import composite, integers, text, lists, SearchStrategy
from gurklang.types import Atom, Put, Value
from typing import Callable, Sequence, Union, Type


_prelude = parse("""
{
    {
        (:true :true) { :true  }
        (_     _    ) { :false }
    } case
} :&& jar

{
    {
        (:false :false) { :false  }
        (_      _     ) { :true   }
    } case
} :|| jar
""")


def _program_evolution(parsed: Sequence[Instruction]) -> str:
    result = [""]
    def print_step(i: Instruction, old_stack: Stack, new_stack: Stack):
        result.append(render_value_as_source(i.as_vec()))
        result.append(stringify_stack(new_stack))
        result.append("")
    run_with_middleware(parsed, middleware=print_step)
    return "\n".join(result)


def _run_test(*xs: Value, code: str, name: str):
    parsed = _prelude + [Put(x) for x in xs] + parse(code)  # type: ignore
    state = run(parsed)
    if state.stack is None:
        assert False, _program_evolution(parsed)
    (head, _) = state.stack
    if head != Atom("true"):
        assert False, _program_evolution(parsed)


def forall(*types: Union[Type[Value], SearchStrategy]):
    def decorator(fn: Callable[..., None]):
        code = fn.__doc__
        name = fn.__name__

        var_names = [f"arg{i}" for i in range(len(types))]
        var_list = ", ".join(var_names)
        exec(dedent(f"""
            def _last_test({var_list}):
                _run_test({var_list}, code={code!r}, name={name!r})
        """), globals())
        global _last_test
        _last_test = wraps(fn)(_last_test)  # type: ignore
        _last_test.__annotations__ = {v: vt for (v, vt) in zip(var_names, types)}  # type: ignore
        _last_test = given(**{
            v: vt if isinstance(vt, SearchStrategy) else infer
            for (v, vt) in zip(var_names, types)})(_last_test)  # type: ignore
        return wraps(fn)(_last_test)
    return decorator


@composite
def atoms(draw):
    return draw(text("abcdefghijklmonqpstuvwxyz0123456789-=<>!?", min_size=1, max_size=16))


@composite
def comparables(draw):
    """
    Strategy for producing a pair of values that are valid for comparison with =
    """
    choice = draw(integers(0, 2))
    if choice == 0:
        return Vec([Int(draw(integers())), Int(draw(integers()))])
    elif choice == 1:
        return Vec([Str("".join(draw(text()))), Str("".join(draw(text())))])
    else:
        xys = draw(lists(comparables()))  # type: ignore
        xs = [v.values[0] for v in xys]
        ys = [v.values[1] for v in xys]
        return Vec([Vec(xs), Vec(ys)])
