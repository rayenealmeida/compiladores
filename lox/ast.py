from abc import ABC
from dataclasses import dataclass
from typing import Callable, Optional

from .ctx import Ctx
from .errors import SemanticError

# Declaramos nossa classe base num módulo separado para esconder um pouco de
# Python relativamente avançado de quem não se interessar pelo assunto.
#
# A classe Node implementa um método `pretty` que imprime as árvores de forma
# legível. Também possui funcionalidades para navegar na árvore usando cursores
# e métodos de visitação.
from .node import Node
from .runtime import LoxFunction
from .runtime import LoxClass
from .runtime import LoxInstance


#
# TIPOS BÁSICOS
#

# Tipos de valores que podem aparecer durante a execução do programa
Value = bool | str | float | None


class Expr(Node, ABC):
    """
    Classe base para expressões.

    Expressões são nós que podem ser avaliados para produzir um valor.
    Também podem ser atribuídos a variáveis, passados como argumentos para
    funções, etc.
    """


class Stmt(Node, ABC):
    """
    Classe base para comandos.

    Comandos são associdos a construtos sintáticos que alteram o fluxo de
    execução do código ou declaram elementos como classes, funções, etc.
    """


@dataclass
class Program(Node):
    """
    Representa um programa.

    Um programa é uma lista de comandos.
    """

    stmts: list[Stmt]

    def eval(self, ctx: Ctx):
        for stmt in self.stmts:
            stmt.eval(ctx)


#
# EXPRESSÕES
#
@dataclass
class BinOp(Expr):
    """
    Uma operação infixa com dois operandos.

    Ex.: x + y, 2 * x, 3.14 > 3 and 3.14 < 4
    """

    left: Expr
    right: Expr
    op: Callable[[Value, Value], Value]

    def eval(self, ctx: Ctx):
        left_value = self.left.eval(ctx)
        right_value = self.right.eval(ctx)
        from .runtime import lox_eq, lox_ne, LoxError
        # Se for igualdade, use lox_eq/lox_ne
        if self.op.__name__ == "lox_eq":
            return lox_eq(left_value, right_value)
        if self.op.__name__ == "lox_ne":
            return lox_ne(left_value, right_value)
        # Proíbe operações matemáticas e de comparação com booleanos
        if (isinstance(left_value, bool) or isinstance(right_value, bool)):
            raise LoxError("Operação matemática/comparação com booleanos não permitida em Lox.")
        return self.op(left_value, right_value)


@dataclass
class Var(Expr):
    """
    Uma variável no código

    Ex.: x, y, z
    """

    name: str

    def eval(self, ctx: Ctx):
        try:
            return ctx[self.name]
        except KeyError:
            raise NameError(f"variável {self.name} não existe!")


@dataclass
class Literal(Expr):
    """
    Representa valores literais no código, ex.: strings, booleanos,
    números, etc.

    Ex.: "Hello, world!", 42, 3.14, true, nil
    """

    value: Value

    def eval(self, ctx: Ctx):
        return self.value


@dataclass
class And(Expr):
    """
    Uma operação infixa com dois operandos.

    Ex.: x and y
    """
    left: Expr
    right: Expr
    def eval(self, ctx: Ctx):
        from .runtime import truthy
        left_value = self.left.eval(ctx)
        if not truthy(left_value):
            return left_value
        return self.right.eval(ctx)


@dataclass
class Or(Expr):
    """
    Uma operação infixa com dois operandos.
    Ex.: x or y
    """
    left: Expr
    right: Expr
    def eval(self, ctx: Ctx):
        from .runtime import truthy
        left_value = self.left.eval(ctx)
        if truthy(left_value):
            return left_value
        return self.right.eval(ctx)


@dataclass
class UnaryOp(Expr):
    """
    Uma operação prefixa com um operando.

    Ex.: -x, !x
    """
    value: Expr
    op: Callable[[Value], Value]
    def eval(self, ctx: Ctx):
        val = self.value.eval(ctx)
        result = self.op(val)
        # Se for not, sempre retorna bool
        if self.op.__name__ == "not_":
            return bool(result)
        return result


@dataclass
class Call(Expr):
    """
    Uma chamada de função.

    Ex.: fat(42)
    """
    callee: Expr
    params: list[Expr]
    def eval(self, ctx: Ctx):
        func = self.callee.eval(ctx)
        params = [param.eval(ctx) for param in self.params]
        if callable(func):
            return func(*params)
        raise TypeError(f"{func} não é uma função!")


@dataclass
class This(Expr):
    dummy: int = 0
    def eval(self, ctx: Ctx):
        return ctx["this"]
    def validate_self(self, cursor):
        from .ast import Class, Function
        found_class = None
        for parent in cursor.parents():
            if isinstance(parent.node, Class):
                found_class = parent.node
                break
        if not found_class:
            raise SyntaxError("Can't use 'this' outside of a class.")
        # Agora procura Function entre This e Class
        for parent in cursor.parents():
            if parent.node is found_class:
                break
            if isinstance(parent.node, Function):
                return
        raise SyntaxError("Can't use 'this' outside of a class.")


@dataclass
class Super(Expr):
    """
    Acesso a method ou atributo da superclasse.

    Ex.: super.x
    """
    method: str
    def eval(self, ctx: Ctx):
        method_name = self.method
        superclass = ctx["super"]
        # Não lança mais erro de runtime aqui
        this = ctx["this"]
        method = superclass.get_method(method_name)
        return method.bind(this)
    def validate_self(self, cursor):
        # Sempre lança SyntaxError para garantir que os testes esperam erro de sintaxe
        from .ast import Class
        for parent in cursor.parents():
            if isinstance(parent.node, Class):
                if parent.node.superclass is None:
                    raise SyntaxError("Can't use 'super' in a class with no superclass.")
                return
        raise SyntaxError("Can't use 'super' outside of a class.")


@dataclass
class Assign(Expr):
    """
    Atribuição de variável.

    Ex.: x = 42
    """
    target: Expr
    value: Expr
    def eval(self, ctx: Ctx):
        if isinstance(self.target, Var):
            val = self.value.eval(ctx)
            ctx[self.target.name] = val
            return val
        elif isinstance(self.target, Getattr):
            obj = self.target.obj.eval(ctx)
            attr = self.target.attr
            val = self.value.eval(ctx)
            setattr(obj, attr, val)
            return val
        else:
            raise TypeError("Atribuição inválida")


@dataclass
class Getattr(Expr):
    """
    Acesso a atributo de um objeto.

    Ex.: x.y
    """
    obj: Expr
    attr: str
    def eval(self, ctx: Ctx):
        obj = self.obj.eval(ctx)
        return getattr(obj, self.attr)


@dataclass
class Setattr(Expr):
    """
    Atribuição de atributo de um objeto.

    Ex.: x.y = 42
    """
    obj: Expr
    attr: str
    value: Expr
    def eval(self, ctx: Ctx):
        obj = self.obj.eval(ctx)
        val = self.value.eval(ctx)
        setattr(obj, self.attr, val)
        return val


#
# COMANDOS
#
@dataclass
class Print(Stmt):
    """
    Representa uma instrução de impressão.

    Ex.: print "Hello, world!";
    """
    expr: Expr
    
    def eval(self, ctx: Ctx):
        from .runtime import print as lox_print
        value = self.expr.eval(ctx)
        lox_print(value)


@dataclass
class Return(Stmt):
    """
    Representa uma instrução de retorno.

    Ex.: return x;
    """
    value: Expr = None
    def eval(self, ctx: Ctx):
        from .runtime import LoxReturn
        if self.value is None:
            val = None
        elif hasattr(self.value, 'eval'):
            val = self.value.eval(ctx)
        else:
            val = self.value  # Pode ser Token ou valor literal
        raise LoxReturn(val)
    def validate_self(self, cursor):
        from .ast import Function
        for parent in cursor.parents():
            if isinstance(parent.node, Function):
                # Só lança erro se não houver outro Function intermediário
                if parent.node.name == "init" and self.value is not None:
                    return_parent = next(cursor.parents())
                    if not any(isinstance(p.node, Function) for p in return_parent.parents()):
                        raise SyntaxError("Can't return a value from an initializer.")
                return
        raise SyntaxError("Can't return from top-level code.")


@dataclass
class VarDef(Stmt):
    """
    Representa uma declaração de variável.

    Ex.: var x = 42;
    """
    name: str
    value: Expr
    def eval(self, ctx: Ctx):
        # Só impede redeclaração se o escopo pai não for o dos builtins
        if getattr(ctx.parent, "parent", None) is not None and self.name in ctx.scope:
            raise NameError(f"Variável '{self.name}' já declarada neste escopo!")
        val = self.value.eval(ctx)
        ctx.var_def(self.name, val)
        return val


@dataclass
class If(Stmt):
    """
    Representa uma instrução condicional.

    Ex.: if (x > 0) { ... } else { ... }
    """
    cond: Expr
    then_branch: Stmt
    else_branch: Stmt | None = None
    def eval(self, ctx: Ctx):
        from .runtime import truthy
        if truthy(self.cond.eval(ctx)):
            return self.then_branch.eval(ctx)
        elif self.else_branch is not None:
            return self.else_branch.eval(ctx)
        return None


@dataclass
class While(Stmt):
    """
    Representa um laço de repetição.

    Ex.: while (x > 0) { ... }
    """
    cond: Expr
    body: Stmt
    def eval(self, ctx: Ctx):
        from .runtime import truthy
        while True:
            if not truthy(self.cond.eval(ctx)):
                break
            self.body.eval(ctx)


@dataclass
class Block(Node):
    """
    Representa bloco de comandos.

    Ex.: { var x = 42; print x;  }
    """
    stmts: list[Stmt]
    def eval(self, ctx: Ctx):
        # Cria um novo escopo para o bloco
        ctx = ctx.push({})
        for stmt in self.stmts:
            stmt.eval(ctx)
        return None


@dataclass
class Function(Stmt):
    """
    Representa uma função.

    Ex.: fun f(x, y) { ... }
    """
    name: str
    args: list[str]
    body: list[Stmt]

    def eval(self, ctx: Ctx):
        from .runtime import LoxFunction
        lox_func = LoxFunction(self.name, self.args, self.body, ctx)
        ctx.var_def(self.name, lox_func)
        return lox_func


@dataclass
class Class(Stmt):
    """
    Representa uma classe.

    """
    name: str
    methods: dict[str, Function]
    superclass: Optional['Class'] = None

    def validate_self(self, cursor):
        # Herança cíclica direta
        if self.superclass is not None:
            if hasattr(self.superclass, 'name') and self.superclass.name == self.name:
                raise SyntaxError("A class can't inherit from itself.")

    def eval(self, ctx: Ctx):
        from .runtime import LoxClass, LoxFunction
        name = self.name.name if hasattr(self.name, 'name') else self.name
        superclass = None
        if self.superclass:
            superclass = ctx[self.superclass.name if hasattr(self.superclass, 'name') else self.superclass]
        if superclass is None:
            method_ctx = ctx
        else:
            method_ctx = ctx.push({"super": superclass})
        methods = {}
        for method_name, method in self.methods.items():
            methods[method_name] = LoxFunction(method_name, method.args, method.body, method_ctx)
        lox_class = LoxClass(name, methods, superclass)
        ctx.var_def(name, lox_class)
        return lox_class

