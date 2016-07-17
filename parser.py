"""The ShivyC parser. It's written entirely by hand because automatic parser
generators are no fun.

"""
import ast

from errors import CompilerError
import token_kinds

class Parser:
    """Provides the parser functionality to convert a list of tokens into an
    AST.

    Each internal function expect_* corresponds to a unique non-terminal symbol
    in the C grammar. It parses the given tokens beginning at the given index to
    try to match a grammar rule that generates the desired symbol. If a match is
    found, it returns a tuple (Node, index) where Node is an AST node for that
    match and index is one more than that of the last token consumed in that
    parse.  If a match is not found, returns (None, 0) and saves the potential
    error to the errors variable.

    errors (List[Tuple[CompilerError, int]]) - Stores a list of compiler errors
    for each time a potential parsing path failed, and the index at which that
    error occurred. If the parse is unsuccessful, we will raise the
    CompilerError that successfully parsed the most tokens.

    """
    def __init__(self):
        self.errors = []

    def parse(self, tokens):
        """Parse the provided list of tokens into an abstract syntax tree (AST)

        tokens (List[Token]) - A list of the tokens, as generated by the lexer
        returns (Node) - The root node of the generated AST"""

        node, index = self.expect_main(tokens, 0)
        if not node:
            # Parsing failed, so we return the error that was most successsful
            # at parsing. If multiple errors parsed the same number of tokens,
            # return the one added later.
            raise sorted(self.errors, key=lambda error: error[1])[-1][0]

        # Ensure there's no tokens left at after the main function
        if tokens[index:]:
            raise self.make_error("unexpected token", index, tokens, self.AT)
        return node

    def expect_main(self, tokens, index):
        """Ex: int main() { return 4; } """

        kinds_before = [token_kinds.int_kw, token_kinds.main,
                        token_kinds.open_paren, token_kinds.close_paren,
                        token_kinds.open_brack]
        match_start = self.match_tokens(tokens[index:], kinds_before)
        if match_start:
            index += match_start
        else:
            err = "expected main function starting"
            return self.add_error(err, index, tokens, self.AT)

        nodes = []
        while True:
            prev_index = index
            node, index = self.expect_statement(tokens, index)
            
            if not node:
                index = prev_index
                break
            else: nodes.append(node)

        if (len(tokens) > index and
            tokens[index].kind == token_kinds.close_brack):
            index += 1
        else:
            err = "expected closing brace"
            return self.add_error(err, index, tokens, self.GOT)
        return (ast.MainNode(nodes), index)

    def expect_statement(self, tokens, index):
        node, index = self.expect_return(tokens, index)
        return (node, index)

    def expect_return(self, tokens, index):
        if len(tokens) > index and tokens[index].kind == token_kinds.return_kw:
            index += 1
        else:
            err = "expected return keyword"
            return self.add_error(err, index, tokens, self.GOT)

        node, index = self.expect_expression(tokens, index)
        if not node:
            return (None, 0)

        if len(tokens) > index and tokens[index].kind == token_kinds.semicolon:
            index += 1
        else:
            err = "expected semicolon"
            return self.add_error(err, index, tokens, self.AFTER)
        return (ast.ReturnNode(node), index)
        
    def expect_expression(self, tokens, index):
        """Ex: 5, 3, etc. Currently only supports single integers.

        We will soon remake this to be a shift-reduce parser."""

        if tokens[index].kind == token_kinds.number:
            return (ast.NumberNode(tokens[index]), index + 1)
        else:
            return self.add_error("expected number", index, tokens, self.GOT)

    #
    # Utility functions for the parser
    #
    
    def match_tokens(self, tokens, kinds_expected):
        """Checks if the provided tokens match the expected token kinds, in
        order. If the tokens all have the expected kind, returns the length of
        kinds_expected. Otherwise, returns 0.

        tokens (List[Token]) - A list of tokens
        expected (List[TokenKind, None]) - A list of token kinds to expect

        """
        if len(tokens) < len(kinds_expected): return False
        if all(kind == token.kind for kind, token
               in zip(kinds_expected, tokens)):
            return len(kinds_expected)
        else: return 0

    # AT generates a message like "expected semicolon at '}'", GOT generates a
    # message like "expected semicolon, got '}'", and AFTER generates a message
    # like "expected semicolon after '15'" (if possible).
    #
    # As a very general guide, use AT when a token should be removed, use AFTER
    # when a token should be to be inserted (esp. because of what came before),
    # and GOT when a token should be changed.
    AT = 1
    GOT = 2
    AFTER = 3 
    def add_error(self, message, index, tokens, message_type):
        """Generates a CompilerError and adds it to the list of errors at the
        given index. For convenience, also returns (None, 0)

        message (str) - the base message to put in the error
        tokens (List[Token]) - a list of tokens
        index (int) - the index of the offending token
        message_type (int) - either self.AT, self.GOT, or self.AFTER. 
        returns - (None, 0)

        """
        self.errors.append(
            (self.make_error(message, index, tokens, message_type),
             index))
        return (None, 0)
        
    def make_error(self, message, index, tokens, message_type):
        """Generate a CompilerError. 

        message (str) - the base message to put in the error
        tokens (List[Token]) - a list of tokens
        index (int) - the index of the offending token
        prefer_after (bool) - if true, tries to generate an error that
        references the token before. e.g. "expected semicolon after 15" when
        true, and "expected semicolon at }" when false.

        """
        if len(tokens) == 0:
            return CompilerError("{} at beginning of source".format(message))

        # If the index is too big, we're always using the AFTER form
        if index >= len(tokens):
            index = len(tokens)
            message_type = self.AFTER
        # If the index is too small, we should not use the AFTER form
        elif index <= 0:
            index = 0
            if message_type == self.AFTER: message_type = self.GOT

        if message_type == self.AT:
            return CompilerError(
                "{} at '{}'".format(message, tokens[index].content),
                tokens[index].file_name, tokens[index].line_num)
        elif message_type == self.GOT:
            return CompilerError(
                "{}, got '{}'".format(message, tokens[index].content),
                tokens[index].file_name, tokens[index].line_num)
        elif message_type == self.AFTER:
            return CompilerError(
                "{} after '{}'".format(message, tokens[index-1].content),
                tokens[index-1].file_name, tokens[index-1].line_num)
        else:
            raise ValueError("Unknown error message type")
