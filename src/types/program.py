import io
from typing import Any, List, Optional, Set, Tuple

from src.types.sized_bytes import bytes32
from src.util.hash import std_hash

from clvm import run_program as default_run_program, KEYWORD_TO_ATOM, SExp
from clvm.casts import int_from_bytes
from clvm.operators import OPERATOR_LOOKUP
from clvm.serialize import sexp_from_stream, sexp_to_stream
from clvm.EvalError import EvalError

from clvm_tools.curry import curry, uncurry

try:
    from clvm_rs import serialize_and_run_program
except ImportError:
    serialize_and_run_program = None


def run_program(
    program,
    args,
    quote_kw=KEYWORD_TO_ATOM["q"],
    apply_kw=KEYWORD_TO_ATOM["a"],
    operator_lookup=OPERATOR_LOOKUP,
    max_cost=None,
    pre_eval_f=None,
):
    return default_run_program(
        program,
        args,
        quote_kw,
        apply_kw,
        operator_lookup,
        max_cost,
        pre_eval_f=pre_eval_f,
    )


class Program(SExp):
    """
    A thin wrapper around s-expression data intended to be invoked with "eval".
    """

    @classmethod
    def parse(cls, f):
        return sexp_from_stream(f, cls.to)

    def stream(self, f):
        sexp_to_stream(self, f)

    @classmethod
    def from_bytes(cls, blob: bytes) -> Any:
        f = io.BytesIO(blob)
        return cls.parse(f)  # type: ignore # noqa

    def __bytes__(self) -> bytes:
        f = io.BytesIO()
        self.stream(f)  # type: ignore # noqa
        return f.getvalue()

    def __str__(self) -> str:
        return bytes(self).hex()

    def _tree_hash(self, precalculated: Set[bytes32]) -> bytes32:
        """
        Hash values in `precalculated` are presumed to have been hashed already.
        """
        if self.listp():
            left = self.to(self.first())._tree_hash(precalculated)
            right = self.to(self.rest())._tree_hash(precalculated)
            s = b"\2" + left + right
        else:
            atom = self.as_atom()
            if atom in precalculated:
                return bytes32(atom)
            s = b"\1" + atom
        return bytes32(std_hash(s))

    def get_tree_hash(self, *args: List[bytes32]) -> bytes32:
        """
        Any values in `args` that appear in the tree
        are presumed to have been hashed already.
        """
        return self._tree_hash(set(args))

    def run_with_cost(self, args) -> Tuple[int, "Program"]:
        prog_args = Program.to(args)
        return run_program(self, prog_args)

    def run(self, args) -> "Program":
        cost, r = self.run_with_cost(args)
        return Program.to(r)

    def curry(self, *args) -> "Program":
        cost, r = curry(self, list(args))
        return Program.to(r)

    def uncurry(self) -> Optional[Tuple["Program", "Program"]]:
        return uncurry(self)

    def as_int(self) -> int:
        return int_from_bytes(self.as_atom())

    def __deepcopy__(self, memo):
        return type(self).from_bytes(bytes(self))

    EvalError = EvalError


def _tree_hash(node: SExp, precalculated: Set[bytes32]) -> bytes32:
    """
    Hash values in `precalculated` are presumed to have been hashed already.
    """
    if node.listp():
        left = _tree_hash(node.first(), precalculated)
        right = _tree_hash(node.rest(), precalculated)
        s = b"\2" + left + right
    else:
        atom = node.as_atom()
        if atom in precalculated:
            return bytes32(atom)
        s = b"\1" + atom
    return bytes32(std_hash(s))


class SerializedProgram:
    """
    An opaque representation of a clvm program. It has a more limited interface than a full SExp
    """

    _buf: bytes = b""

    @classmethod
    def parse(cls, f) -> "SerializedProgram":
        tmp = sexp_from_stream(f, SExp.to)
        return SerializedProgram.from_bytes(tmp.as_bin())

    def stream(self, f):
        f.write(self._buf)

    @classmethod
    def from_bytes(cls, blob: bytes) -> "SerializedProgram":
        ret = SerializedProgram()
        ret._buf = bytes(blob)
        return ret

    def __bytes__(self) -> bytes:
        return self._buf

    def __str__(self) -> str:
        return bytes(self).hex()

    def get_tree_hash(self, *args: List[bytes32]) -> bytes32:
        """
        Any values in `args` that appear in the tree
        are presumed to have been hashed already.
        """
        print(self._buf)
        print(type(self._buf))
        assert type(self._buf) == bytes
        tmp = sexp_from_stream(io.BytesIO(self._buf), SExp.to)
        return _tree_hash(tmp, set(args))

    def run_with_cost(self, args) -> Tuple[int, SExp]:
        assert type(self._buf) == bytes
        if type(args) == SerializedProgram:
            prog_args = args._buf
            assert type(args._buf) == bytes
        else:
            prog_args = SExp.to(args).as_bin()
        max_cost = 0
        cost, ret = serialize_and_run_program(self._buf, prog_args, 1, 3, max_cost)
        return cost, sexp_from_stream(io.BytesIO(ret), SExp.to)

    def run(self, args) -> "Program":
        cost, r = self.run_with_cost(args)
        return Program.to(r)
