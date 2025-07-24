"""
Implementa o transformador da árvore sintática que converte entre as representações

    lark.Tree -> lox.ast.Node.

A resolução de vários exercícios requer a modificação ou implementação de vários
métodos desta classe.
"""

from typing import Callable
from lark import Transformer, v_args

from . import runtime as op
from .ast import *


def op_handler(op: Callable):
    """
    Fábrica de métodos que lidam com operações binárias na árvore sintática.

    Recebe a função que implementa a operação em tempo de execução.
    """

    def method(self, left, right):
        return BinOp(left, right, op)

    return method


RESERVED_WORDS = {"and", "class", "else", "false", "for", "fun", "if", "nil", "or", "print", "return", "super", "this", "true", "var", "while"}

@v_args(inline=True)
class LoxTransformer(Transformer):
    # Programa
    def program(self, *stmts):
        return Program(list(stmts))

    # Operações matemáticas básicas
    mul = op_handler(op.mul)
    div = op_handler(op.truediv)
    sub = op_handler(op.sub)
    add = op_handler(op.add)

    # Comparações
    gt = op_handler(op.gt)
    lt = op_handler(op.lt)
    ge = op_handler(op.ge)
    le = op_handler(op.le)
    eq = op_handler(op.lox_eq)
    ne = op_handler(op.lox_ne)

    and_op = lambda self, left, right: And(left, right)
    or_op = lambda self, left, right: Or(left, right)

    def not_op(self, value):
        from .runtime import not_ as lox_not
        return UnaryOp(value, lox_not)
    def neg(self, value):
        from .runtime import neg as lox_neg
        return UnaryOp(value, lox_neg)

    def assign(self, target, value):
        if isinstance(target, Getattr):
            return Setattr(target.obj, target.attr, value)
        return Assign(target, value)

    def getattr(self, obj, attr):
        return Getattr(obj, attr.name if isinstance(attr, Var) else attr)

    def call(self, base, *calls_and_attrs):
        expr = base
        calls_and_attrs = list(calls_and_attrs)
        while calls_and_attrs:
            item = calls_and_attrs.pop(0)
            if isinstance(item, list):
                expr = Call(expr, item)
            elif isinstance(item, Var):
                expr = Getattr(expr, item.name)
        return expr

    def params(self, *args):
        return list(args)

    def var_decl(self, name, value=None):
        import inspect
        if hasattr(name, '__class__') and name.__class__.__name__ == 'Literal':
            raise SyntaxError(f"Nome de variável inválido: {name}")
        if hasattr(name, 'name'):
            name_str = name.name
        elif hasattr(name, 'value'):
            name_str = str(name.value)
        else:
            name_str = str(name)
        if name_str in RESERVED_WORDS:
            raise SyntaxError(f"Nome de variável reservado: {name_str}")
        stack = inspect.stack()
        for frame in stack:
            if 'expr' in frame.function:
                raise SyntaxError("Declaração de variável não pode ser usada como expressão.")
        if value is None:
            from .ast import Literal
            value = Literal(None)
        return VarDef(name_str, value)

    def block(self, *stmts):
        local_vars = set()
        stmts_list = []
        for stmt in stmts:
            if isinstance(stmt, VarDef):
                varname = stmt.name if isinstance(stmt.name, str) else str(stmt.name)
                if varname in local_vars:
                    raise SyntaxError(f"Variável local duplicada: {varname}")
                local_vars.add(varname)
            stmts_list.append(stmt)
        return Block(stmts_list)

    def if_cmd(self, cond, then_branch, else_branch=None):
        return If(cond, then_branch, else_branch)

    def print_cmd(self, _print_token, expr):
        if isinstance(expr, Var):
            return Print(self.VAR(expr.name, context="expr"))
        return Print(expr)

    def VAR(self, token, context=None):
        name = str(token)
        if name == "true":
            from .ast import Literal
            return Literal(True)
        if name == "false":
            from .ast import Literal
            return Literal(False)
        if name == "nil":
            from .ast import Literal
            return Literal(None)
        if name == "this":
            from .ast import This
            return This()
        if context == "expr" and name in {"return", "super", "class", "fun", "var", "for", "while", "if", "else", "print", "or", "and"}:
            raise SyntaxError(f"Uso inválido de palavra reservada em expressão: {name}")
        return Var(name)

    def NUMBER(self, token):
        num = float(token)
        return Literal(num)
    
    def STRING(self, token):
        text = str(token)[1:-1] 
        text = text.replace('\\n', '\\n')
        text = text.replace('\\r', '\\r')
        text = text.replace('\\t', '\\t')
        text = text.replace('\\\\', '\\')
        return Literal(text)
    
    def NIL(self, _):
        return Literal(None)

    def BOOL(self, token):
        print(f"DEBUG BOOL chamado com token: {token}")
        return Literal(token == "true")

    def method_decl(self, name, params, body):
        if isinstance(body, Block):
            body_stmts = body.stmts
        else:
            body_stmts = [body]
        param_names = [p.name if hasattr(p, 'name') else p for p in params]
        return (name.name if isinstance(name, Var) else name, Function(name.name if isinstance(name, Var) else name, param_names, body_stmts))

    def class_decl(self, *args):
        if len(args) == 4:
            _, name, superclass, body = args
        elif len(args) == 3:
            _, name, body = args
            superclass = None
        else:
            raise Exception('class_decl: argumentos inesperados')
        if hasattr(body, 'children'):
            body = body.children
        methods = {k: v for k, v in (body or [])}
        class_node = Class(name.name if isinstance(name, Var) else name, methods=methods, superclass=superclass)
        # Valida todos os métodos no contexto da classe
        from lox.node import Cursor
        class_cursor = Cursor(class_node)
        for method in methods.values():
            if hasattr(method, 'validate_tree'):
                method_cursor = Cursor(method, class_cursor)
                for cursor in method_cursor.descendants():
                    cursor.node.validate_self(cursor)
        return class_node

    def return_stmt(self, *args):
        from .ast import Return
        exprs = [a for a in args if not (hasattr(a, 'type') and a.type == 'RETURN')]
        if exprs:
            return Return(exprs[0])
        else:
            return Return(None)

    def function_decl(self, _fun_token, name, params, body):
        if isinstance(body, Block):
            body_stmts = body.stmts
        else:
            body_stmts = [body]
        param_names = []
        for p in params:
            if hasattr(p, 'name'):
                pname = p.name
            elif hasattr(p, 'value'):
                raise SyntaxError(f"Nome de parâmetro inválido: {p}")
            else:
                pname = str(p)
            param_names.append(pname)
        seen = set()
        for p in param_names:
            if p in RESERVED_WORDS:
                raise SyntaxError(f"Nome de parâmetro reservado: {p}")
            if p in seen:
                raise SyntaxError(f"Parâmetro duplicado: {p}")
            seen.add(p)
        if isinstance(body, Block):
            local_vars = set()
            for stmt in body.stmts:
                if isinstance(stmt, VarDef):
                    if stmt.name in param_names:
                        raise SyntaxError(f"Variável local colide com parâmetro: {stmt.name}")
                    if stmt.name in local_vars:
                        raise SyntaxError(f"Variável local duplicada: {stmt.name}")
                    local_vars.add(stmt.name)
        return Function(name.name if hasattr(name, 'name') else name, param_names, body_stmts)

    def while_cmd(self, cond, body):
        return While(cond, body)

    def for_cmd(self, init, cond, incr, body):
        from .ast import Block, While
        if incr is not None:
            body = Block([body, incr])
        if cond is None:
            from .ast import Literal
            cond = Literal(True)
        loop = While(cond, body)
        if init is not None:
            return Block([init, loop])
        return loop

    def for_init(self, *args):
        if not args:
            return None
        return args[0]

    def for_cond(self, *args):
        if not args:
            return None
        return args[0]

    def for_incr(self, *args):
        if not args:
            return None
        return args[0]

    def simple_stmt(self, stmt):
        return stmt

    def super_getattr(self, _super_token, attr):
        return Super(attr.name if isinstance(attr, Var) else attr)