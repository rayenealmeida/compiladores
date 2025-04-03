from typing import Any

def json(src: str) -> Any:
    chars = list(reverted(chars))
    print(char.pop())

#def read_literal
def read_value(chars: list[str]):
    ws (chars)
    match chars[-1]:
        case "t":
            value = read_true(chars)
        case "f":
            value = read_false(chars)
        case "n":
            value = read_null(chars)
#def read_true:

#def read_false:


#def rasd_null:

def read_number(chars: list[str], value):
    ns=[]
    if chars[-1] == "0":
        chars.pop()
        return 0
    while len(chars) > 0 and chars[-1] in "0123456789":
        n = chars.pop()
        ns.append(n)
    return int("".join(ns))

def read_string(chars: list[str]) -> str:
    if chars.pop() != '"':
        raise SyntaxError
    parts = []
    while (c :=chars.pop()) != '"':
        parts.append(c)
    return '"'.join(parts)

def ws():
    pass

def read_array(chars: list[str]):
    if chars.pop() != "[":
        raise SyntaxError
    ws(chars)

    if chars[-1] == "]":
        chars.pop()
        return []
    while True:
        values = read_value(chars)
        read_value(chars)
        c=chars.pop()
        if c ==",":
            continue

        elif c == "]":
            break
        else:
            raise SyntaxError
    return values

if __name__ == '__main__':
    print(json("null"))
    print(json("42"+ 1))
    print(json('"Ray"') + 1)
    print(json('[i, "Raye", "Compiladores"]'))