import io

from clvm.SExp import SExp
from clvm.casts import int_from_bytes
from clvm.serialize import sexp_from_stream
from clvm import to_sexp_f


NULL = b""
OPT = True
#OPT = False

class LazySExp: #(SExp):
    """ LazySExp is a drop-in replacement for SExp that stores its internal data
        as serialized bytes until forced to convert to an SExp tree representation.

        Note that a conversion is only done once, and methods like cons currently 
        return SExp, not LazySExp
    """
    true: "LazySExp"
    false: "LazySExp"
    __null__: "LazySExp"

    def _convert(self):
        if not self.sexp:
            self.sexp = sexp_from_stream(io.BytesIO(self.binary), to_sexp_f)
            import inspect
            print(f"{self.__class__.__name__} converted in {inspect.stack()[1].function} {self.sexp}")  # noqa TODO use log

    def __init__(self, binary):
        self.binary : bytes = binary
        self.sexp : SExp = None

    def as_pair(self):
        self._convert()
        return self.sexp.as_pair()

    def as_atom(self):
        self._convert()
        return self.sexp.as_atom()

    def listp(self):
        self._convert()
        return self.sexp.listp()

    def nullp(self):
        if OPT:
            return self.binary == b"\x80"
        else:
            self._convert()
            return self.sexp.nullp()

    def as_int(self):
        if OPT:
            # if not atom, throw
            if self.binary[0] == b"\xff":
                raise ExecError("as_int on cons {self.binary}")
            return int_from_bytes(self.binary)
        else:
            self._convert()
            return int_from_bytes(self.sexp.atom)

    def as_bin(self):
        return self.binary

    @classmethod
    def to(class_, v):
        self._convert()
        return self.sexp.to(class_, v)

    def cons(self, right: "CLVMObject"):
        if OPT:
            return self.__class__(NULL.join([b"\xff", self.binary, right.as_bin()]))
        else:
            self._convert()
            return self.sexp.cons(right)

    def first(self):
        self._convert()
        return self.sexp.first()

    def rest(self):
        self._convert()
        return self.sexp.rest()

    @classmethod
    def null(class_):
        return class_.__null__

    def as_iter(self):
        self._convert()
        return self.sexp.as_iter()

    def __eq__(self, other):
        self._convert()
        return self.sexp.__eq__(other)

    def list_len(self):
        self._convert()
        return self.sexp.list_len()

    def as_python(self):
        self._convert()
        return as_python(self.sexp)

    def __str__(self):
        return self.binary.hex()

    def __repr__(self):
        #self._convert()
        #return self.sexp.__repr__()
        #return "SExp(%s)" % (str(self))
        return "%s(%s)" % (self.__class__.__name__, str(self))

LazySExp.false = LazySExp.__null__ = SExp.__null__
LazySExp.true = SExp.true
