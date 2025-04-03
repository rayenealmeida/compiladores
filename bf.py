import sys
import click

class BF:
    def __init__(self):
        self.memory = [0] * 10_000
        self.index = 0
    def run(self, src: str):
        chars = iter(src)
        for c in chars:
            match c:
                case ">":
                    self.index +=1
                case "<":
                    if self.index == 0:
                        raise IndexError
                    self.index -= 1
                case "+":
                    self.memory[self.index] =  (self.memory[self.index] +1) % 256
                case "-":
                    self.memory[self.index] = (self.memory[self.index] -1) % 256
                case ".":
                    print(chr(self.memory[self.index]), end = "")
                case ",":
                    self.memory[self.index] = ord(click.getchar(echo = True)) % 256
                case "[":
                    cmd = []
                    ooen_paren = 1
                    for c in chars:
                        if c == "]":
                            open_paren -=1
                        if c == "[":
                            open_paren += 1
                        if open_paren ==0:
                            break
                        cmd.append(c)
                    else:
                        raise SyntaxError
                