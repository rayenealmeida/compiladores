import builtins
from dataclasses import dataclass
from operator import add, eq, ge, gt, le, lt, mul, ne, neg, not_, sub, truediv
from typing import TYPE_CHECKING

from .ctx import Ctx

if TYPE_CHECKING:
    from .ast import Stmt, Value

__all__ = [
    "add",
    "lox_eq",
    "lox_ne",
    "ge",
    "gt",
    "le",
    "lt",
    "mul",
    "neg",
    "not_",
    "print",
    "show",
    "sub",
    "truthy",
    "truediv",
]


class LoxBoundMethod:
    def __init__(self, function, instance):
        self.function = function
        self.instance = instance
    def __call__(self, *args):
        return self.function.bind(self.instance)(*args)
    def __eq__(self, other):
        return self is other
    def __hash__(self):
        return id(self)
    def __str__(self):
        return str(self.function)


class LoxInstance:
    """
    Classe base para todos os objetos Lox.
    """

    def __init__(self):
        self.klass = None
        self.fields = {}

    def __getattr__(self, name):
        if name in self.fields:
            return self.fields[name]
        # Se for método init chamado na instância, retorna wrapper que sempre retorna self
        if name == "init" and hasattr(self.klass, "methods") and "init" in self.klass.methods:
            method = self.klass.methods["init"].bind(self)
            def init_wrapper(*args):
                try:
                    method(*args)
                except Exception as e:
                    # Se for LoxReturn, ignora o valor e retorna self
                    from .runtime import LoxReturn
                    if isinstance(e, LoxReturn):
                        pass
                    else:
                        raise
                return self
            return init_wrapper
        if self.klass:
            method = self.klass.get_method(name)
            from .runtime import LoxBoundMethod
            return LoxBoundMethod(method, self)
        raise AttributeError(f"Atributo {name} não encontrado")

    def __setattr__(self, key, value):
        if key in {"klass", "fields"}:
            object.__setattr__(self, key, value)
        else:
            self.fields[key] = value

    def __str__(self):
        return f"{self.klass.name} instance"


@dataclass
class LoxFunction:
    """
    Classe base para todas as funções Lox.
    """

    name: str
    args: list[str]
    body: list["Stmt"]
    ctx: Ctx

    def __call__(self, *args):
        env = dict(zip(self.args, args, strict=True))
        env = self.ctx.push(env)

        try:
            for stmt in self.body:
                stmt.eval(env)
        except LoxReturn as e:
            return e.value

    def bind(self, this):
        # Cria um novo contexto com 'this' ligado à instância
        return LoxFunction(self.name, self.args, self.body, self.ctx.push({"this": this}))

    def __str__(self):
        return f"<fn {self.name}>"

    def __eq__(self, other):
        return self is other
    def __hash__(self):
        return id(self)

    def __setattr__(self, key, value):
        if key in {"name", "args", "body", "ctx"}:
            object.__setattr__(self, key, value)
        else:
            from .errors import SemanticError as LoxError
            raise LoxError("Only instances have fields.")


class LoxReturn(Exception):
    """
    Exceção para retornar de uma função Lox.
    """

    def __init__(self, value):
        self.value = value
        super().__init__()


class LoxError(Exception):
    """
    Exceção para erros de execução Lox.
    """


nan = float("nan")
inf = float("inf")


def print(value: "Value"):
    """
    Imprime um valor lox.
    """
    builtins.print(show(value))


def show(value: "Value") -> str:
    """
    Converte valor lox para string.
    """
    # Funções Lox
    if hasattr(value, "__class__") and value.__class__.__name__ == "LoxFunction":
        return str(value)
    # Classes Lox
    if hasattr(value, "__class__") and value.__class__.__name__ == "LoxClass":
        return str(value.name)
    # Funções nativas (qualquer callable que não seja LoxFunction)
    if callable(value) and (not hasattr(value, "__class__") or value.__class__.__name__ != "LoxFunction"):
        return "<native fn>"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "nil"
    if isinstance(value, float):
        # Imprimir inteiros sem ponto decimal
        if value.is_integer():
            return str(int(value))
        return str(value)
    return str(value)


def show_repr(value: "Value") -> str:
    """
    Mostra um valor lox, mas coloca aspas em strings.
    """
    if isinstance(value, str):
        return f'"{value}"'
    return show(value)


# Garante que not_ sempre retorna bool Python
def truthy(value: "Value") -> bool:
    """
    Converte valor lox para booleano segundo a semântica do lox.
    """
    if value is None or value is False:
        return False
    return True

def not_(value):
    return not truthy(value)


def lox_eq(a, b):
    # nil só é igual a nil
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    # tipos diferentes nunca são iguais
    if type(a) != type(b):
        return False
    return a == b

def lox_ne(a, b):
    return not lox_eq(a, b)


class LoxClass:
    def __init__(self, name=None, methods=None, superclass=None):
        self.name = name or "<class>"
        self.methods = methods or {}
        self.superclass = superclass

    def get_method(self, name):
        if name in self.methods:
            return self.methods[name]
        if self.superclass:
            return self.superclass.get_method(name)
        raise AttributeError(f"Método {name} não encontrado em {self.name}")

    def __call__(self, *args):
        instance = LoxInstance()
        instance.klass = self
        initializer = self.methods.get("init")
        if initializer:
            initializer.bind(instance)(*args)
            return instance
        else:
            if args:
                from .errors import SemanticError as LoxError
                raise LoxError(f"Expected 0 arguments but got {len(args)}.")
            return instance

    def __str__(self):
        return str(self.name)

    def __setattr__(self, key, value):
        if key in {"name", "methods", "superclass"}:
            object.__setattr__(self, key, value)
        else:
            from .errors import SemanticError as LoxError
            raise LoxError("Only instances have fields.")
