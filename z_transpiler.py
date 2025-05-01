import re
import sys
import os
import json 
import traceback

# --- Global Configuration & Constants ---
TEMPLATE_FILE = "z_templates.txt"
RUNTIME_HEADER = "z_runtime.h"
RUNTIME_SOURCE = "z_runtime.c" # Used only for gcc command hint

# --- 1. Load C Code Templates ---
CODE_TEMPLATES = {}

def load_templates_from_file(filename=TEMPLATE_FILE):
    """Reads the template file and stores snippets in CODE_TEMPLATES."""
    templates = {}
    current_key = None
    current_lines = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                match = re.match(r'^\s*\*\*\*\s*(.*?)\s*\*\*\*\s*$', line)
                if match:
                    if current_key and current_lines:
                        templates[current_key] = "".join(current_lines)
                    current_key = match.group(1).strip()
                    # Normalize keys for easier access (optional)
                    current_key = current_key.upper().replace(' ', '_')
                    current_lines = []
                    # print(f"Found template key: {current_key}") # Debug
                elif current_key:
                    current_lines.append(line)
            # Add the last template block
            if current_key and current_lines:
                templates[current_key] = "".join(current_lines)
        # print(f"Loaded {len(templates)} templates.") # Debug
        return templates
    except FileNotFoundError:
        print(f"Error: Template file '{filename}' not found!", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading template file '{filename}': {e}", file=sys.stderr)
        sys.exit(1)

# --- 2. Z Language Token Definitions (derived from user JSON) ---
TOKEN_SPECIFICATION = [
    ('COMMENT_BLOCK_CURLY', r'\{.*?\}'),
    ('COMMENT_BLOCK_SLASH', r'/\*.*?\*/'),
    ('NEWLINE',             r'\n'),
    ('SKIP',                r'[ \t]+'),
    ('ASSIGN',              r':='),
    # Keywords (Order matters: ENDIF before END, etc.)
    ('IF',                  r'\bIF\b'),
    ('THEN',                r'\bTHEN\b'), # Added THEN based on common usage
    ('ELSE',                r'\bELSE\b'),
    ('ENDIF',               r'\bENDIF\b'),
    ('WHILE',               r'\bWHILE\b|\bWH\b'),
    ('DO',                  r'\bDO\b'), # Added DO based on common usage
    ('ENDWHILE',            r'\bENDWHILE\b|\bEWH\b'),
    ('FOR',                 r'\bFOR\b'),
    ('FROM',                r'\bFROM\b'), # Added FROM based on common usage
    ('TO',                  r'\bTO\b'),
    ('ENDFOR',              r'\bENDFOR\b|\bEFOR\b'),
    ('ACTION',              r'\bACTION|ACTIONS\b'),
    ('FUNCTION',            r'\bFUNCTION|FUNCTIONS\b'),
    ('BEGIN',               r'\bBEGIN\b'),
    ('END',                 r'\bEND\b'),
    ('LET',                 r'\bLET\b'), # Declaration keyword
    ('CALL',                r'\bCALL\b'), # Procedure call
    ('POINTER',             r'\bPOINTER\b'),
    ('OF',                  r'\bOF\b'),
    ('STRUCTURE',           r'\bSTRUCTURE\b'),
    ('ARRAY',               r'\bARRAY|ARRAYS\b'),
    ('LIST',                r'\bLIST|LISTS\b'),
    ('BILIST',              r'\bBILIST\b'),
    ('QUEUE',               r'\bQUEUE|QUEUES\b'),
    ('STACK',               r'\bSTACK|STACKS\b'),
    ('BST',                 r'\bBST\b'),
    ('MST',                 r'\bMST\b'), # M-ary Search Tree
    ('FILE',                r'\bFILE\b'),
    ('HEADER',              r'\bHEADER\b'),
    ('BUFFER',              r'\bBUFFER\b'),
    ('DYNAMIC',             r'\bDYNAMIC\b'),
    # Types
    ('INTEGER',             r'\bINTEGER|INTEGERS\b'),
    ('BOOLEAN',             r'\bBOOLEAN|BOOLEANS\b'),
    ('CHAR',                r'\bCHAR|CHARACTER|CHARACTERS\b'),
    ('STRING',              r'\bSTRING|STRINGS|CHAINE|CHAINES\b'),
    # Builtins / ADT Functions (Add ALL from JSON grammar)
    ('MOD',                 r'\bMOD\b'),
    ('MAX',                 r'\bMAX\b'),
    ('MIN',                 r'\bMIN\b'),
    ('EXP',                 r'\bEXP\b'),
    ('RANDNUMBER',          r'\bRANDNUMBER|ALEANUMBER\b'),
    ('RANDSTRING',          r'\bRANDSTRING|ALEACHAINE\b'),
    ('CHARACT',             r'\bCHARACT\b'), # Map to ZGetCharStr
    ('STRINGLENGTH',        r'\bLENTHSTRING|STRINGLENGTH\b'), # Map to ZStringLength
    ('CREATE_LIST',         r'\bCREATE_LIST|CREER_LISTE\b'), # W Creer_liste
    ('CREATE_BILIST',       r'\bCREATE_BILIST|CREER_LISTEBI\b'), # W Creer_listebi
    ('CREATE_STACK',        r'\bCREATE_STACK|CREER_PILE\b'), # W Creer_pile
    ('CREATE_QUEUE',        r'\bCREATE_QUEUE|CREER_QUEUE|CREERFILE\b'), # W Creer_file
    ('CREATE_BST',          r'\bCREATE_BST|CREATE_ARB|CREER_ARB\b'), # W Creer_arb
    ('CREATE_MST',          r'\bCREATE_MST|CREATE_ARM|CREER_ARM\b'), # Creer_arm
    ('INIT_STRUCT',         r'\bINIT_STRUCT\b'), # W Init_struct
    ('INIT_ARRAY',          r'\bINIT_ARRAY|INIT_VECT|INIT_TAB\b'), # W Init_vect
    ('ALLOCATE',            r'\bALLOCATE|ALLOUER|ALLOC_STRUCT|ALLOC_TAB|ALLOCATE_CELL|ALLOCATE_NODE|CREERNOEUD\b'), # Map based on context
    ('FREE',                r'\bFREE|LIBERER|LIBER_TAB|LIBERERNOEUD|LIBER_STRUCT\b'), # Map based on context
    ('VALUE',               r'\bCELL_VALUE|VALUE|VALEUR|INFO|NODE_VALUE|NODE_VALUE_MST|INFOR\b'), # Map based on context
    ('ASS_VAL',             r'\bASS_VAL|AFF_VAL|AFF_INFO|ASS_NODE_VAL|AFF_NODE_VAL_MST|AFF_INFOR\b'), # Map based on context
    ('NEXT',                r'\bNEXT|SUIVANT\b'),
    ('PREVIOUS',            r'\bPREVIOUS|PRECEDENT\b'),
    ('ASS_ADR',             r'\bASS_ADR|AFF_ADR|AFF_ADRD\b'), # Map based on context (List vs BiList)
    ('ASS_L_ADR',           r'\bASS_L_ADR|AFF_ADRG\b'), # BiList specific
    ('PUSH',                r'\bPUSH|EMPILER\b'),
    ('POP',                 r'\bPOP|DEPILER\b'),
    ('EMPTY_STACK',         r'\bEMPTY_STACK|PILEVIDE\b'),
    ('ENQUEUE',             r'\bENQUEUE|ENFILER\b'),
    ('DEQUEUE',             r'\bDEQUEUE|DEFILER\b'),
    ('EMPTY_QUEUE',         r'\bEMPTY_QUEUE|FILEVIDE\b'),
    ('LC',                  r'\bLC|FG\b'), # Left Child
    ('RC',                  r'\bRC|FD\b'), # Right Child
    ('PARENT',              r'\bPARENT|PERE\b'),
    ('ASS_LC',              r'\bASS_LC|AFF_FG\b'),
    ('ASS_RC',              r'\bASS_RC|AFF_FD\b'),
    ('ASS_PARENT',          r'\bASS_PARENT|AFF_PERE\b'),
    ('CHILD',               r'\bCHILD|FILS\b'), # M-ary
    ('ASS_CHILD',           r'\bASS_CHILD|AFF_FILS\b'), # M-ary
    ('DEGREE',              r'\bDEGREE|DEGRE\b'), # M-ary
    ('ASS_DEGREE',          r'\bASS_DEGREE|AFF_DEGRE\b'), # M-ary
    ('ELEMENT',             r'\bELEMENT\b'), # Array access
    ('ASS_ELEMENT',         r'\bASS_ELEMENT|AFF_ELEMENT\b'), # Array assign
    ('STRUCT',              r'\bSTRUCT\b'), # Struct field access (e.g., S.Field or Struct(S, Field)?) - Assuming S.Field is used
    ('ASS_STRUCT',          r'\bASS_STRUCT|AFF_STRUCT\b'), # Struct field assign
    ('OPEN',                r'\bOPEN|OUVRIR\b'),
    ('CLOSE',               r'\bCLOSE|FERMER\b'),
    ('READSEQ',             r'\bREADSEQ|LIRESEQ\b'),
    ('WRITESEQ',            r'\bWRITESEQ|ECRIRESEQ\b'),
    ('READDIR',             r'\bREADDIR|LIREDIR\b'),
    ('WRITEDIR',            r'\bWRITEDIR|ECRIREDIR\b'),
    ('ADD',                 r'\bADD|RAJOUTER\b'), # File append
    ('ENDFILE',             r'\bENDFILE|FINFICH\b'),
    ('ALLOC_BLOCK',         r'\bALLOC_BLOCK|ALLOC_BLOC\b'),
    ('ACCESS_HEADER',       r'\bHEADER|HEADSEQ\b'), # Access header 
    ('ASS_HEADER',          r'\bASS_HEADER|AFF_ENTETE\b'), # Assign header
    # IO
    ('READ',                r'\bREAD|LIRE\b'),
    ('WRITE',               r'\bWRITE|ECRIRE\b'),
    # Literals
    ('NUMBER',              r'\b\d+\b'),
    ('STRING_LIT_DQ',       r'"(?:\\.|[^"\\])*"'), # Double-quoted string
    ('STRING_LIT_SQ',       r"'(?:\\.|[^'\\])*'"), # Single-quoted string (treat same as double?)
    ('BOOLEAN_LIT',         r'\bTRUE|FALSE\b'),
    ('NULL_LIT',            r'\bNULL|NIL\b'),
    # Operators (Order for <=, >=, <>)
    ('LTE',                 r'<='),
    ('GTE',                 r'>='),
    ('NEQ',                 r'<>|#'),
    ('LT',                  r'<'),
    ('GT',                  r'>'),
    ('EQ',                  r'='), # Comparison, not assignment
    ('PLUS',                r'\+'),
    ('MINUS',               r'-'),
    ('MULTIPLY',            r'\*'),
    ('DIVIDE',              r'/'),
    ('AND',                 r'\bAND\b'), # Logical operators
    ('OR',                  r'\bOR\b'),
    ('NOT',                 r'\bNOT\b'),
    # Punctuation
    ('LPAREN',              r'\('),
    ('RPAREN',              r'\)'),
    ('LBRACKET',            r'\['),
    ('RBRACKET',            r'\]'),
    ('LBRACE',              r'\{'), # For structure definitions? Check Z syntax
    ('RBRACE',              r'\}'),
    ('COMMA',               r','),
    ('COLON',               r':'),
    ('SEMICOLON',           r';'),
    ('DOT',                 r'\.'), # For struct field access like S.Field?
    # Identifiers must be last
    ('IDENTIFIER',          r'\b[A-Za-z][A-Za-z0-9_]*\b'),
    ('MISMATCH',            r'.'), # Any other character
]

# --- 3. Tokenizer ---
def tokenize(code):
    """Generator that yields Tokens from the input code string."""
    tok_regex = '|'.join(f'(?P<{pair[0]}>{pair[1]})' for pair in TOKEN_SPECIFICATION)
    line_num = 1
    line_start = 0
    # Precompile regex for efficiency
    compiled_regex = re.compile(tok_regex, re.DOTALL | re.IGNORECASE) # Add IGNORECASE? Z seems case-insensitive from grammar
    pos = 0
    while pos < len(code):
        mo = compiled_regex.match(code, pos)
        if mo is None:
            # No token matched, advance one character and report error
            # This simple error handling might misreport line number on multi-line comments etc.
            col = pos - line_start
            raise RuntimeError(f"Unexpected character '{code[pos]}' on line {line_num}, column {col}")
            # pos += 1 # Or try to recover by skipping? Risky.

        kind = mo.lastgroup
        value = mo.group()
        pos = mo.end()

        if kind == 'NEWLINE':
            line_start = pos
            line_num += 1
            continue # Skip newline tokens for parser simplicity
        elif kind == 'SKIP' or kind.startswith('COMMENT'):
            # Need to adjust line_num if comment contains newlines
            line_num += value.count('\n')
            if '\n' in value:
                line_start = pos - value.rfind('\n') - 1
            continue
        elif kind == 'MISMATCH':
            # This should theoretically not be reached if regex covers everything
            col = mo.start() - line_start
            raise RuntimeError(f"Internal Tokenizer Error: Mismatch token '{value}' on line {line_num}, column {col}")

        col = mo.start() - line_start
        yield Token(kind, value, line_num, col)


class Token:
    def __init__(self, type, value, line, column):
        self.type = type.upper() # Normalize type name
        self.value = value
        self.line = line
        self.column = column
    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, L{self.line}:{self.column})"

# --- 4. Symbol Table and Type Mapping ---
class SymbolTable:
    def __init__(self):
        self.scopes = [{}] # Stack of scopes, global scope first

    def enter_scope(self):
        self.scopes.append({})

    def exit_scope(self):
        if len(self.scopes) > 1:
            self.scopes.pop()

    def declare(self, name, info):
        """Declare a symbol in the current scope."""
        # Could check for redeclaration here
        self.scopes[-1][name.upper()] = info # Store uppercase name

    def lookup(self, name):
        """Look up a symbol starting from current scope up to global."""
        uname = name.upper()
        for scope in reversed(self.scopes):
            if uname in scope:
                return scope[uname]
        return None

symbol_table = SymbolTable()

# Keep track of defined types (structs, files, etc.)
type_definitions = {}

def ztype_to_ctype(z_type_info):
    """Maps Z type info (dict) to C type string (base type mainly)."""
    # Ensure z_type_info is a dictionary, handle simple type names if passed directly
    if isinstance(z_type_info, str):
         z_kind = z_type_info.upper() # Treat string as kind if passed directly
         z_base = z_kind
         z_size = None
         z_name = z_kind
    elif isinstance(z_type_info, dict):
         z_kind = z_type_info.get('kind', '').upper()
         z_base = z_type_info.get('base_type', '').upper()
         z_size = z_type_info.get('size')
         z_name = z_type_info.get('name', '').upper() # For struct/file names
    else:
        return "void /* unknown type info format */" # Handle unexpected input

    if z_kind == 'INTEGER': return 'int'
    if z_kind == 'BOOLEAN': return 'bool'
    if z_kind == 'CHAR': return 'char'
    if z_kind == 'STRING':
        # For STRING, the base C type is char. Size is handled at declaration.
        # Distinguish pointer (no size) vs fixed array (has size) later if needed
        return 'char' # Return base type 'char'
        # Old: return f'char[{z_size + 1}]' if z_size else 'char*'
    if z_kind == 'POINTER':
        pointed_ctype = "void" # Default if pointed_type is missing
        if 'pointed_type' in z_type_info and z_type_info['pointed_type']:
             pointed_ctype = ztype_to_ctype(z_type_info['pointed_type'])
        return f"{pointed_ctype}*"
    if z_kind == 'ARRAY':
         element_ctype = "void" # Default if element_type is missing
         if 'element_type' in z_type_info and z_type_info['element_type']:
              element_ctype = ztype_to_ctype(z_type_info['element_type'])
         # Return base element type. Dimensions handled at declaration.
         return element_ctype
         # Old: dims_str = "".join([f"[{d}]" for d in z_type_info['dimensions']])
         # Old: return f"{element_ctype} /*{dims_str}*/"
    if z_kind == 'STRUCTURE':
        # Return the C typedef name if available, else struct tag
        struct_def = type_definitions.get(z_name) # z_name should be struct Z name
        if struct_def and 'c_typedef' in struct_def:
             return struct_def['c_typedef']
        else: # Fallback
             return f"struct {z_name}_t" # Use struct tag convention

    if z_kind == 'STRUCTURE_POINTER':
        # Return the C pointer typedef name if available
        struct_def = type_definitions.get(z_base) # z_base should be struct Z name
        if struct_def and 'c_ptr_typedef' in struct_def:
             return struct_def['c_ptr_typedef']
        else: # Fallback
             return f"struct {z_base}_t*"

    if z_kind == 'FILE':
         return "FILE*" # Standard C file pointer

    if z_kind.endswith('_POINTER') and z_base: # Generic handling for ListPtr etc.
         base_type_def = type_definitions.get(z_base)
         if base_type_def and 'c_ptr_typedef' in base_type_def:
              return base_type_def['c_ptr_typedef']
         else: # Fallback if specific pointer typedef not found
              return f"void* /* unknown ADT pointer: {z_base} */"

    # Default: Assume it's a known C type or a typedef name passed directly
    return z_kind if isinstance(z_kind, str) and z_kind else "void /* unknown */"


# --- 5. Transpiler Core Logic ---
class Transpiler:
    def __init__(self, tokens):
        self.tokens = list(tokens) # Work with a list for lookahead/rewind
        self.token_index = 0
        self.current_token = self.tokens[self.token_index] if self.tokens else None

        self.c_code_parts = {
            "includes": set([f'#include "{RUNTIME_HEADER}"']), # Include runtime header
            "macros": [], # For #define constants like Ordre_arm
            "typedefs": [], # Type definitions (structs, pointers)
            "globals": [], # Global C variable declarations
            "functions": [], # C Function definitions (helpers, actions)
            "main": ["    srand(time(NULL)); // Initialize random seed"] # Code for the main function
        }
        self.indent_level = 1 # Start inside main
        self.current_section = "main" # Default section to add code
        self.function_return_type = None # Track return type for RETURN statements

    def add_code(self, code_line, section=None, indent=None):
        if section is None: section = self.current_section
        if indent is None: indent = self.indent_level
        # Adjust indent for global scope items
        effective_indent = indent if section in ["main", "functions"] else 0
        prefix = "    " * effective_indent
        self.c_code_parts[section].append(prefix + code_line)

    def next_token(self):
        self.token_index += 1
        if self.token_index < len(self.tokens):
            self.current_token = self.tokens[self.token_index]
            return self.current_token
        else:
            self.current_token = None
            return None

    def peek_token(self, offset=1):
        peek_index = self.token_index + offset
        return self.tokens[peek_index] if peek_index < len(self.tokens) else None

    def expect(self, *token_types):
        """Consumes the current token if it matches one of the expected types."""
        if self.current_token and self.current_token.type in token_types:
            token = self.current_token
            self.next_token()
            return token
        else:
            expected = " or ".join(token_types)
            found = self.current_token.type if self.current_token else 'EOF'
            line = self.current_token.line if self.current_token else '?'
            col = self.current_token.column if self.current_token else '?'
            raise SyntaxError(f"Expected {expected} but found {found} on Line {line}:{col}")

    def consume_optional(self, *token_types):
        """Consumes the current token if it matches, otherwise does nothing."""
        if self.current_token and self.current_token.type in token_types:
            token = self.current_token
            self.next_token()
            return token
        return None

    # --- Main Parsing Logic ---
    def parse(self):
        """Main parsing loop."""
        while self.current_token:
            # Top-level constructs
            if self.consume_optional('LET'):
                self.parse_declaration("globals") # Assume top-level LET is global
            elif self.current_token.type in ['FUNCTION', 'ACTION']:
                self.parse_function_definition()
            elif self.consume_optional('STRUCTURE'):
                 self.parse_structure_definition()
            elif self.consume_optional('ARRAY'): # Declaration like ARRAY T[10] OF INTEGER
                 self.parse_array_declaration("globals") # Assuming top-level array def is global var
            elif self.consume_optional('FILE'):
                 self.parse_file_type_definition()
            # Add parsing for LIST, QUEUE, STACK, BST, MST type definitions if Z has them
            # Main program block
            elif self.consume_optional('BEGIN'):
                self.current_section = "main"
                self.indent_level = 1
                self.parse_block() # Parse the main program block
                self.expect('END')
                self.consume_optional('SEMICOLON') # Optional semicolon after main END?
            else:
                 # Skip unexpected tokens at top level for robustness? Or raise error?
                 raise SyntaxError(f"Unexpected token {self.current_token} at top level.")
                 # self.next_token() # Skip

        return self.assemble_c_code()

    def parse_block(self):
        """Parses statements within BEGIN/END, IF/ENDIF, WHILE/ENDWHILE, etc."""
        # Assumes the block start token (BEGIN, THEN, DO) was already consumed
        end_tokens = {'BEGIN': 'END', 'IF': 'ENDIF', 'ELSE': 'ENDIF', 'WHILE': 'ENDWHILE', 'FOR': 'ENDFOR'}
        block_starter_token = self.tokens[self.token_index-1] # Crude way to get context

        while self.current_token and self.current_token.type not in ['END', 'ENDIF', 'ELSE', 'ENDWHILE', 'ENDFOR']:
             statement_handled = self.parse_statement()
             if not statement_handled:
                  raise SyntaxError(f"Unexpected token {self.current_token} inside block on line {self.current_token.line}")
             # Require semicolons between statements? Z syntax unclear. Assuming yes.
             if self.current_token and self.current_token.type not in ['END', 'ENDIF', 'ELSE', 'ENDWHILE', 'ENDFOR']:
                 self.expect('SEMICOLON')
             # Handle optional semicolons before block enders
             self.consume_optional('SEMICOLON')


    def parse_statement(self):
        """Parses a single statement."""
        if self.consume_optional('LET'):
            self.parse_declaration(self.current_section)
            return True
        elif self.consume_optional('IF'):
            self.parse_if_statement()
            return True
        elif self.consume_optional('WHILE'):
             self.parse_while_loop()
             return True
        elif self.consume_optional('FOR'):
             self.parse_for_loop()
             return True
        elif self.consume_optional('WRITE'):
            self.parse_io_statement('WRITE')
            return True
        elif self.consume_optional('READ'):
             self.parse_io_statement('READ')
             return True
        elif self.consume_optional('CALL'): # Handle procedure calls
             self.parse_procedure_call()
             return True
        elif self.consume_optional('RETURN'): # Handle function return
             self.parse_return_statement()
             return True
        elif self.current_token.type == 'IDENTIFIER':
             # Could be assignment (Var := Expr) or implicit procedure call?
             # Let's assume assignment is the only possibility without CALL
             self.parse_assignment()
             return True

        # Add cases for other specific statements (e.g., list ops, tree ops)
        # Check for built-in ADT functions as statements (e.g., PUSH(S, V))
        # This part needs more knowledge of Z's exact syntax for ADT operations

        return False # No matching statement found


    def parse_declaration(self, section):
        """Parses `Var : Type` or `Var1, Var2 : Type`"""
        # --- All code below MUST be indented relative to this 'def' ---
        var_names = []
        start_token = self.current_token # Keep track for error messages
        while True:
            ident_token = self.expect('IDENTIFIER')
            var_names.append(ident_token.value)
            if not self.consume_optional('COMMA'):
                break
        self.expect('COLON')

        # This call uses 'self', so it must be inside the method
        z_type_info = self.parse_type() # Gets {'kind': 'STRING', 'size': 50} etc.

        # This call uses 'self', so it must be inside the method
        base_c_type = ztype_to_ctype(z_type_info) # Note: ztype_to_ctype is currently global, but could be self.ztype_to_ctype if moved into class

        if not base_c_type:
             raise TypeError(f"Unknown Z type '{z_type_info.get('kind','?')}' for variable(s) starting with '{var_names[0]}' near Line {start_token.line if start_token else '?'}")

        # This loop must be inside the method
        for var_name in var_names:
            c_decl = f"{base_c_type} {var_name}" # Start with type and name

            z_kind = z_type_info.get('kind', '').upper()
            if z_kind == 'STRING' and 'size' in z_type_info and z_type_info['size'] is not None:
                 c_decl += f"[{z_type_info['size'] + 1}]"
            elif z_kind == 'ARRAY' and 'dimensions' in z_type_info:
                 dims_str = "".join([f"[{d}]" for d in z_type_info['dimensions']])
                 c_decl += dims_str

            c_decl += ";"

            # This call uses 'self', so it must be inside the method
            symbol_table.declare(var_name, {'z_type': z_type_info, 'c_type': base_c_type, 'name': var_name}) # symbol_table is global, but could be self.symbol_table

            # This call uses 'self', so it must be inside the method
            self.add_code(c_decl, section=section)

    def parse_array_declaration(self, section):
         """ Parses `T : ARRAY [d1, d2] OF Type` (as type) OR `ARRAY T[d1] OF Type` (as var) """
         # This logic assumes `ARRAY T[d1] OF Type` is a variable declaration
         # If `ARRAY [...] OF Type` is just a type specifier, call parse_type instead
         var_name = self.expect('IDENTIFIER').value
         dims = []
         self.expect('LBRACKET')
         while True:
             dim_token = self.expect('NUMBER')
             dims.append(int(dim_token.value))
             if not self.consume_optional('COMMA'): break
         self.expect('RBRACKET')
         self.expect('OF')
         element_type_info = self.parse_type()
         element_ctype = ztype_to_ctype(element_type_info)

         # Combine info for symbol table
         array_type_info = {
             'kind': 'ARRAY',
             'name': var_name, # Or maybe generate a unique type name
             'element_type': element_type_info,
             'dimensions': dims
         }
         c_dims_str = "".join([f"[{d}]" for d in dims])
         c_decl = f"{element_ctype} {var_name}{c_dims_str};"

         symbol_table.declare(var_name, {'z_type': array_type_info, 'c_type': c_decl, 'name': var_name})
         self.add_code(c_decl, section=section)


    def parse_type(self):
        """Parses a type definition. Returns dict describing the type."""
        token = self.current_token
        type_info = {'kind': token.type} # Start with the token type

        if token.type == 'INTEGER': self.next_token(); return {'kind': 'INTEGER'}
        if token.type == 'BOOLEAN': self.next_token(); return {'kind': 'BOOLEAN'}
        if token.type == 'CHAR': self.next_token(); return {'kind': 'CHAR'}

        if token.type == 'STRING':
            self.next_token()
            size = None
            if self.consume_optional('LBRACKET'):
                size_token = self.expect('NUMBER')
                size = int(size_token.value)
                self.expect('RBRACKET')
            type_info['size'] = size # None if dynamic (CHAINE), value if fixed size
            return type_info

        if token.type == 'POINTER':
            self.next_token()
            self.expect('TO')
            type_info['pointed_type'] = self.parse_type()
            return type_info

        if token.type == 'ARRAY':
            self.next_token()
            dims = []
            self.expect('LBRACKET')
            while True:
                dim_token = self.expect('NUMBER')
                dims.append(int(dim_token.value))
                if not self.consume_optional('COMMA'): break
            self.expect('RBRACKET')
            self.expect('OF')
            type_info['element_type'] = self.parse_type()
            type_info['dimensions'] = dims
            return type_info

        if token.type == 'FILE': # File type reference
             self.next_token();
             # Need to know the specific file type name declared earlier?
             # Or just treat 'FILE' as the type? Assume 'FILE' maps to C FILE*
             return {'kind': 'FILE'} # Generic file type

        # Add LIST, BILIST, STACK, QUEUE, BST, MST handling if they are types
        # e.g., LIST OF INTEGER
        if token.type in ['LIST', 'BILIST', 'STACK', 'QUEUE', 'BST', 'MST']:
             kind = token.type
             self.next_token()
             self.expect('OF')
             element_type = self.parse_type()
             # We need a unique name for this specific list/stack/etc type
             type_name = f"{kind}_{element_type.get('kind','?')}" # Simple naming
             type_info = {'kind': kind, 'element_type': element_type, 'name': type_name}
             # Generate the C typedefs/structs for this ADT now? Or when declared?
             # Let's assume the C types are generated elsewhere based on templates
             # Return info describing the Z type
             return {'kind': f"{kind}_POINTER", 'base_type': type_name} # Assume variables hold pointers

        if token.type == 'IDENTIFIER': # Could be a custom struct type, file type, etc.
            type_name = token.value
            self.next_token()
            # Look up if this identifier is a known type
            if type_name.upper() in type_definitions:
                 defined_info = type_definitions[type_name.upper()]
                 # If it's a struct, return info indicating it's a struct *instance* type
                 if defined_info['kind'] == 'STRUCTURE':
                     # Variables usually hold structs by value or pointer? Z seems pointer-oriented.
                     # Let's assume declaration `LET S : MyStruct` means `S` is a pointer.
                     return {'kind': 'STRUCTURE_POINTER', 'base_type': defined_info['name']}
                 elif defined_info['kind'] == 'FILE':
                     # Variables of a specific file type hold FILE*
                     return {'kind': 'FILE', 'base_type': defined_info['name']}
                 else:
                     # Could be a typedef name for a basic type, array, pointer etc.
                     return defined_info # Return the stored type info
            else:
                 # Assume it's a type name we haven't processed yet or simple C type? Risky.
                 return {'kind': type_name} # Pass identifier through

        raise SyntaxError(f"Unexpected token in type definition: {token}")


    def parse_assignment(self):
        """Parses Target := Expression"""
        # Current token should be the identifier target
        target_expr_code, target_info = self.parse_target_expression() # Parses V, V[i], S.Field etc.

        self.expect('ASSIGN')
        source_expr_code, source_info = self.parse_expression() # Parses the RHS

        # Generate C assignment code, considering types ($AFF logic)
        c_assign = self.generate_assignment_code(target_expr_code, target_info, source_expr_code, source_info)
        self.add_code(c_assign + ";")

    def parse_target_expression(self):
        """Parses the LHS of an assignment (variable, array element, struct field). Returns C code and type info."""
        if self.current_token.type == 'IDENTIFIER':
            base_name = self.current_token.value
            base_info = symbol_table.lookup(base_name)
            if not base_info: raise NameError(f"Variable '{base_name}' not declared before assignment at Line {self.current_token.line}")
            self.next_token()

            target_code = base_name
            current_info = base_info

            while self.current_token and self.current_token.type in ['LBRACKET', 'DOT']:
                if self.consume_optional('LBRACKET'): # Array Indexing
                    if current_info['z_type']['kind'] != 'ARRAY':
                         raise TypeError(f"Attempting to index non-array '{target_code}' at Line {self.current_token.line}")

                    indices_code = []
                    while True:
                        indices_code.append(self.parse_expression()[0]) # Get C code for index expression
                        if not self.consume_optional('COMMA'): break
                    self.expect('RBRACKET')

                    # TODO: Need proper C index calculation (AUTRES2 from templates)
                    # This is complex, requires knowing dimensions. Simplification:
                    c_indices = "".join([f"[{code}]" for code in indices_code])
                    target_code += c_indices
                    current_info = {'z_type': current_info['z_type']['element_type'], 'c_type': ztype_to_ctype(current_info['z_type']['element_type'])} # Type of the element

                elif self.consume_optional('DOT'): # Struct Field Access
                    if current_info['z_type']['kind'] not in ['STRUCTURE', 'STRUCTURE_POINTER']:
                         raise TypeError(f"Attempting field access on non-structure '{target_code}' at Line {self.current_token.line}")

                    field_name = self.expect('IDENTIFIER').value
                    struct_name = current_info['z_type']['base_type']
                    struct_def = type_definitions.get(struct_name.upper())
                    if not struct_def: raise TypeError(f"Definition for struct type '{struct_name}' not found.")

                    field_info = None
                    for f in struct_def['fields']:
                         if f['name'].upper() == field_name.upper():
                              field_info = f
                              break
                    if not field_info: raise NameError(f"Structure '{struct_name}' has no field named '{field_name}' at Line {self.current_token.line}")

                    # C code uses -> for pointers, . for values. Assume pointers based on Z type.
                    target_code += f"->{field_name}" # Assume target_code holds pointer variable
                    current_info = {'z_type': field_info['z_type'], 'c_type': field_info['c_type']} # Type of the field

                else: break # Should not happen

            return target_code, current_info
        else:
            raise SyntaxError(f"Expected identifier for assignment target, found {self.current_token} at Line {self.current_token.line}")

    def generate_assignment_code(self, target_c, target_info, source_c, source_info):
        """Generates C code for assignment using $AFF logic based on types."""
        # TODO: This needs much more robust type checking and handling
        target_ctype = target_info['c_type']
        target_zkind = target_info['z_type']['kind']
        # source_ctype = source_info['c_type'] if source_info else None
        source_zkind = source_info['z_type']['kind'] if source_info else None

        # Handle string assignment ($AFF -> strcpy)
        # Check if target is char[] or char*
        if isinstance(target_ctype, str) and ('char*' in target_ctype or target_ctype.startswith('char[')):
             # Check if source is string literal or char*/char[] variable
             # Simplistic check:
             if source_zkind == 'STRING' or (isinstance(source_c, str) and source_c.startswith('"')):
                  return f'strcpy({target_c}, {source_c})' # Potential buffer overflow if fixed size!
             else:
                 # Assigning non-string to string target? Error or default.
                 print(f"Warning: Assigning potentially non-string '{source_c}' to string target '{target_c}' at Line {self.current_token.line if self.current_token else '?'}", file=sys.stderr)
                 return f'{target_c} = ({target_ctype}) {source_c}' # Fallback to basic assignment with cast? Risky.

        # Handle struct assignment ($AFF -> memcpy or helper func?)
        if target_zkind in ['STRUCTURE', 'STRUCTURE_POINTER'] or source_zkind in ['STRUCTURE', 'STRUCTURE_POINTER']:
             # Need to ensure types are compatible
             # Option 1: Use memcpy (requires target is addressable, source is addressable)
             # Need size of the struct type
             struct_name = target_info['z_type'].get('base_type') or source_info['z_type'].get('base_type')
             struct_def = type_definitions.get(struct_name.upper()) if struct_name else None
             if struct_def:
                  struct_c_name = struct_def['c_struct_name']
                  # Assume target_c is pointer, source_c might be value or pointer
                  # This requires knowing if source_c is address (&source_c) or pointer (source_c)
                  # Simplified memcpy assuming both are pointers/addressable
                  # return f'memcpy({target_c}, {source_c}, sizeof(struct {struct_c_name}))'
                  # Let's use simple assignment for now, assuming C allows struct assignment
                  return f'*{target_c} = *({struct_c_name}*)({source_c})' # Dereference pointers? Very complex.

        # Default: Basic assignment
        return f'{target_c} = {source_c}'


    # --- Expression Parsing (Simplified) ---
    # TODO: Implement proper precedence climbing or recursive descent for operators
    def parse_expression(self):
        """Parses an expression. Returns (c_code_string, type_info_dict). Simplified."""
        # For now, just parse a single term
        return self.parse_term()

     # --- Expression Parsing (Improved - Basic Precedence) ---

    def parse_expression(self):
        """Parses an expression (entry point). Returns (c_code, type_info)."""
        # Currently, highest level is comparison. Add logical AND/OR later if needed.
        return self.parse_comparison()

    def parse_comparison(self):
        """Parses comparison operators (=, <>, <, >, <=, >=)."""
        left_code, left_info = self.parse_additive() # Parse left side (arithmetic)

        while self.current_token and self.current_token.type in ['EQ', 'NEQ', 'LT', 'GT', 'LTE', 'GTE']:
            op_token = self.current_token
            self.next_token()
            right_code, right_info = self.parse_additive() # Parse right side (arithmetic)

            # TODO: Add type checking - numeric vs string comparison
            # TODO: Use $COMPAR logic -> strcmp for strings
            op_map = {'EQ': '==', 'NEQ': '!=', 'LT': '<', 'GT': '>', 'LTE': '<=', 'GTE': '>='}
            c_op = op_map.get(op_token.type)

            # Handle string comparison (basic - assumes non-null)
            if left_info.get('c_type') == 'char*' or right_info.get('c_type') == 'char*':
                 left_code = f"(strcmp({left_code}, {right_code}) {c_op} 0)"
            else: # Assume numeric comparison
                 left_code = f"({left_code} {c_op} {right_code})"

            # Result of a comparison is always boolean
            left_info = {'kind': 'BOOLEAN', 'c_type': 'bool'}

        return left_code, left_info

    def parse_additive(self):
        """Parses additive operators (+, -)."""
        left_code, left_info = self.parse_multiplicative() # Parse left term (multiplication)

        while self.current_token and self.current_token.type in ['PLUS', 'MINUS']:
            op_token = self.current_token
            self.next_token()
            right_code, right_info = self.parse_multiplicative() # Parse right term (multiplication)

            # TODO: Add type checking (e.g., string concatenation?)
            op_map = {'PLUS': '+', 'MINUS': '-'}
            c_op = op_map.get(op_token.type)

            left_code = f"({left_code} {c_op} {right_code})"
            # Type propagation: Assume result stays numeric if inputs are. Needs refinement.
            if left_info.get('c_type') == 'int' and right_info.get('c_type') == 'int':
                 left_info = {'kind': 'INTEGER', 'c_type': 'int'}
            else: # Fallback - could be float, error, etc.
                 left_info = {'kind': 'UNKNOWN', 'c_type': '/*unknown*/'}


        return left_code, left_info

    def parse_multiplicative(self):
        """Parses multiplicative operators (*, /)."""
        left_code, left_info = self.parse_term() # Parse base factor

        while self.current_token and self.current_token.type in ['MULTIPLY', 'DIVIDE', 'MOD']: # Added MOD
            op_token = self.current_token
            self.next_token()
            right_code, right_info = self.parse_term() # Parse next factor

            # TODO: Add type checking
            op_map = {'MULTIPLY': '*', 'DIVIDE': '/', 'MOD': '%'} # Original MOD maps to C %
            c_op = op_map.get(op_token.type)

            # Special handling for Z's MOD function vs C operator?
            # If MOD token corresponds to the runtime function Mod(), generate call
            if op_token.type == 'MOD':
                 # Check if we should use the Mod() function from runtime
                 # Let's assume the Z operator MOD directly maps to C % for integers for now
                 if left_info.get('c_type') == 'int' and right_info.get('c_type') == 'int':
                     left_code = f"({left_code} {c_op} {right_code})"
                 else: # Use function call for non-int or if defined that way
                     left_code = f"Mod({left_code}, {right_code})" # Assumes Mod() exists and takes compatible types
            else: # Standard multiply/divide
                 left_code = f"({left_code} {c_op} {right_code})"

            # Type propagation - Assume int result for now. Needs float handling.
            if left_info.get('c_type') == 'int' and right_info.get('c_type') == 'int':
                 left_info = {'kind': 'INTEGER', 'c_type': 'int'}
            else:
                 left_info = {'kind': 'UNKNOWN', 'c_type': '/*unknown*/'}

        return left_code, left_info

        # --- Adjust parse_term slightly (optional: add unary +/-) ---
    def parse_term(self):
        """ Parses a single term/factor. Returns (c_code_string, type_info_dict)."""
        token = self.current_token
        unary_op = None
        if token.type in ['PLUS', 'MINUS']:
             unary_op = token.value
             self.next_token()
             token = self.current_token

        term_code, term_info = None, None

        if token.type == 'NUMBER':
            self.next_token()
            # CORRECTED STRUCTURE
            term_code, term_info = token.value, {'z_type': {'kind': 'INTEGER'}, 'c_type': 'int'}
        elif token.type == 'STRING_LIT_DQ' or token.type == 'STRING_LIT_SQ':
            self.next_token()
            # CORRECTED STRUCTURE
            term_code, term_info = token.value, {'z_type': {'kind': 'STRING', 'size': None}, 'c_type': 'char*'}
        elif token.type == 'BOOLEAN_LIT':
            self.next_token()
            c_val = token.value.lower()
            # CORRECTED STRUCTURE
            term_code, term_info = c_val, {'z_type': {'kind': 'BOOLEAN'}, 'c_type': 'bool'}
        elif token.type == 'NULL_LIT':
            self.next_token()
            # CORRECTED STRUCTURE
            term_code, term_info = "NULL", {'z_type': {'kind': 'POINTER', 'pointed_type': {'kind':'VOID'}}, 'c_type': 'void*'} # Added nested kind

        elif token.type == 'IDENTIFIER':
            if self.peek_token() and self.peek_token().type == 'LPAREN':
                 term_code, term_info = self.parse_function_call()
            else:
                 term_code, term_info = self.parse_target_expression() # This already returns the correct structure

        elif token.type == 'LPAREN':
            self.next_token()
            term_code, term_info = self.parse_expression() # Assumes parse_expression returns correct structure
            self.expect('RPAREN')
            # return f"({term_code})", term_info # Don't add extra parens

        elif token.type == 'NOT':
             self.next_token()
             operand_code, operand_info = self.parse_term()
             term_code = f"(!{operand_code})"
             # CORRECTED STRUCTURE
             term_info = {'z_type': {'kind': 'BOOLEAN'}, 'c_type': 'bool'} # Result of NOT is boolean

        else:
            raise SyntaxError(f"Unexpected token in expression term: {token}")

        if unary_op:
             term_code = f"({unary_op}{term_code})"
             # term_info should already be set correctly (e.g., for numbers)
             # Add type check if needed: if term_info['z_type']['kind'] != 'INTEGER': raise TypeError...

        # --- ENSURE term_info is not None before returning ---
        if term_info is None:
             # This should ideally not happen if all cases are covered
             raise RuntimeError(f"Internal Error: Term info not generated for token {token} in parse_term")

        return term_code, term_info # Return the potentially modified code and info

        

    def parse_function_call(self):
         """ Parses `FunctionName(arg1, arg2, ...)` returns (c_code_string, type_info_dict) """
         func_name_token = self.expect('IDENTIFIER')
         func_name = func_name_token.value
         uname = func_name.upper()

         self.expect('LPAREN')
         args_c_code = []
         args_info = []
         if not self.consume_optional('RPAREN'): # Check if args exist
              while True:
                   arg_code, arg_info = self.parse_expression()
                   args_c_code.append(arg_code)
                   args_info.append(arg_info)
                   if not self.consume_optional('COMMA'):
                        break
              self.expect('RPAREN')

         # Map Z function names to C names from runtime/templates/generated code
         # TODO: Improve mapping and type checking based on function signatures
         c_func_name = func_name # Default
         return_info = {'kind': 'UNKNOWN', 'c_type': 'void'} # Default return type

         # Builtins from z_runtime
         if uname == 'MOD': c_func_name = 'Mod'; return_info = {'kind':'INTEGER', 'c_type':'int'}
         if uname == 'MIN': c_func_name = 'Min'; return_info = {'kind':'INTEGER', 'c_type':'int'}
         if uname == 'MAX': c_func_name = 'Max'; return_info = {'kind':'INTEGER', 'c_type':'int'}
         if uname == 'EXP': c_func_name = 'Exp'; return_info = {'kind':'INTEGER', 'c_type':'int'}
         if uname in ['RANDNUMBER', 'ALEANUMBER']: c_func_name = 'Aleanombre'; return_info = {'kind':'INTEGER', 'c_type':'int'}
         if uname in ['RANDSTRING', 'ALEACHAINE']: c_func_name = 'Aleachaine'; return_info = {'kind':'STRING', 'c_type':'char*'} # Caller must free
         if uname == 'CHARACT': c_func_name = 'ZGetCharStr'; return_info = {'kind':'STRING', 'c_type':'char*'} # Caller must free
         if uname in ['LENTHSTRING', 'STRINGLENGTH']: c_func_name = 'ZStringLength'; return_info = {'kind':'INTEGER', 'c_type':'int'}

         # TODO: Add mappings for ALL ADT functions (List, File, Tree etc.)
         # This requires knowing the generated C function names based on type placeholders

         # Check if it's a user-defined function/action
         func_symbol = symbol_table.lookup(func_name)
         if func_symbol and func_symbol['z_type']['kind'] in ['FUNCTION', 'ACTION']:
              c_func_name = func_symbol['name'] # Use declared name
              return_info = func_symbol['z_type']['return_type'] if func_symbol['z_type']['kind'] == 'FUNCTION' else {'kind':'VOID', 'c_type':'void'}

         call_code = f"{c_func_name}({', '.join(args_c_code)})"
         return call_code, return_info

    def parse_procedure_call(self):
         """ Parses CALL Proc(arg1, arg2, ...) ; """
         # CALL keyword already consumed
         call_c_code, _ = self.parse_function_call() # Re-use function call parsing logic
         self.add_code(call_c_code + ";")

    def parse_return_statement(self):
         """ Parses RETURN Expression? """
         # RETURN keyword consumed
         return_c_code = ""
         return_info = {'kind':'VOID', 'c_type':'void'}
         if not self.consume_optional('SEMICOLON'): # Check if expression follows
             return_c_code, return_info = self.parse_expression()
             # TODO: Type check against self.function_return_type

         self.add_code(f"return {return_c_code};")


    # --- Control Flow ---
    def parse_if_statement(self):
         """ Parses IF condition THEN ... ELSE ... ENDIF """
         # IF consumed
         condition_c_code, _ = self.parse_expression()
         self.consume_optional('THEN') # Optional THEN

         self.add_code(f"if ({condition_c_code}) {{")
         self.indent_level += 1
         self.parse_block() # Parse the THEN block
         self.indent_level -= 1
         self.add_code("}")

         if self.consume_optional('ELSE'):
              self.add_code("else {")
              self.indent_level += 1
              self.parse_block() # Parse the ELSE block
              self.indent_level -= 1
              self.add_code("}")

         self.expect('ENDIF')

    def parse_while_loop(self):
        """ Parses WHILE condition DO ... ENDWHILE """
        # WHILE consumed
        condition_c_code, _ = self.parse_expression()
        self.consume_optional('DO') # Optional DO

        self.add_code(f"while ({condition_c_code}) {{")
        self.indent_level += 1
        self.parse_block() # Parse the loop body
        self.indent_level -= 1
        self.add_code("}")
        self.expect('ENDWHILE')

    def parse_for_loop(self):
         """ Parses FOR var FROM start TO end DO ... ENDFOR """
         # FOR consumed
         loop_var_token = self.expect('IDENTIFIER')
         loop_var = loop_var_token.value
         # Ensure loop variable is declared (implicitly as int if not?)
         var_info = symbol_table.lookup(loop_var)
         if not var_info:
              print(f"Warning: Loop variable '{loop_var}' not declared, assuming int at Line {loop_var_token.line}", file=sys.stderr)
              self.add_code(f"int {loop_var};", section=self.current_section) # Declare locally
              symbol_table.declare(loop_var, {'z_type': {'kind':'INTEGER'}, 'c_type': 'int', 'name': loop_var})
         elif var_info['c_type'] != 'int':
              raise TypeError(f"FOR loop variable '{loop_var}' must be INTEGER, not {var_info['c_type']} at Line {loop_var_token.line}")

         self.consume_optional('ASSIGN') # Allow := or FROM
         self.consume_optional('FROM')

         start_expr, _ = self.parse_expression()
         self.expect('TO')
         end_expr, _ = self.parse_expression()
         self.consume_optional('DO')

         # Generate C for loop (simple ascending step 1)
         self.add_code(f"for ({loop_var} = {start_expr}; {loop_var} <= {end_expr}; ++{loop_var}) {{")
         self.indent_level += 1
         self.parse_block() # Parse the loop body
         self.indent_level -= 1
         self.add_code("}")
         self.expect('ENDFOR')


    # --- IO Statements ---
    def parse_io_statement(self, io_type):
         """ Parses READ(...) or WRITE(...) """
         # READ/WRITE consumed
         self.expect('LPAREN')
         format_string_parts = []
         args_c_code = []
         is_first_arg = True
         while not self.consume_optional('RPAREN'):
              if not is_first_arg: self.expect('COMMA')

              if io_type == 'WRITE':
                   expr_c_code, expr_info = self.parse_expression()
                   # Infer basic format specifier (needs improvement)
                   c_type = expr_info.get('c_type', 'void')
                   fmt = "%s" # Default
                   if c_type == 'int': fmt = "%d"
                   elif c_type == 'bool': fmt = "%d" # Print 0 or 1
                   elif c_type == 'char': fmt = "%c"
                   elif 'char*' in c_type or c_type.startswith('char['): fmt = "%s"
                   # Add float, etc. if Z supports them
                   format_string_parts.append(fmt)
                   args_c_code.append(expr_c_code)
              else: # READ
                   # Read expects variables as targets
                   target_c_code, target_info = self.parse_target_expression()
                   c_type = target_info.get('c_type', 'void')
                   fmt = "%s" # Default
                   arg = f"&{target_c_code}" # Default: pass address
                   if c_type == 'int': fmt = "%d"
                   elif c_type == 'bool':
                        fmt = "%d" # Read as int, requires temp var or careful handling post-scan
                        print(f"Warning: Reading BOOLEAN using %d, store result manually for '{target_c_code}'", file=sys.stderr)
                   elif c_type == 'char': fmt = " %c" # Skip whitespace
                   elif c_type.startswith('char['): # Fixed buffer
                        fmt = "%s" # Unsafe, use width limit?
                        arg = target_c_code # Array name is pointer
                   elif 'char*' in c_type:
                        raise TypeError(f"Cannot READ directly into 'char*' ('{target_c_code}') at Line {self.current_token.line if self.current_token else '?'}. Allocate memory first.")
                   # Add float etc.
                   format_string_parts.append(fmt)
                   args_c_code.append(arg)

              is_first_arg = False

         # Assemble C call
         format_string = " ".join(format_string_parts)
         if io_type == 'WRITE':
              format_string += "\\n" # Add newline to WRITE automatically?
              c_call = "printf"
         else: # READ
              c_call = "scanf"

         c_args_str = ", ".join(args_c_code)
         self.add_code(f'{c_call}("{format_string}"{", " + c_args_str if c_args_str else ""});')


    # --- Definitions ---
    def parse_function_definition(self):
        """ Parses FUNCTION Name(params) : ReturnType ... END or ACTION Name(params) ... END """
        is_action = self.current_token.type == 'ACTION'
        self.expect('FUNCTION' if not is_action else 'ACTION')
        func_name = self.expect('IDENTIFIER').value
        self.add_code(f"// Function/Action: {func_name}", section="functions", indent=0)

        # Enter new scope for parameters and locals
        symbol_table.enter_scope()

        # Parse parameters
        params_info = []
        params_c_parts = []
        self.expect('LPAREN')
        if not self.consume_optional('RPAREN'):
             while True:
                  param_name = self.expect('IDENTIFIER').value
                  self.expect('COLON')
                  param_z_type = self.parse_type()
                  param_c_type = ztype_to_ctype(param_z_type)
                  params_info.append({'name': param_name, 'z_type': param_z_type, 'c_type': param_c_type})
                  params_c_parts.append(f"{param_c_type} {param_name}")
                  # Declare param in current scope
                  symbol_table.declare(param_name, {'name': param_name, 'z_type': param_z_type, 'c_type': param_c_type})
                  if not self.consume_optional('COMMA'): break
             self.expect('RPAREN')

        # Parse return type for FUNCTION
        return_z_type = {'kind':'VOID', 'c_type':'void'}
        if not is_action:
             self.expect('COLON')
             return_z_type = self.parse_type()
        return_c_type = ztype_to_ctype(return_z_type)
        self.function_return_type = return_z_type # Store for checking RETURN statements

        # Store function signature in symbol table (global scope?)
        func_info = {
             'name': func_name,
             'kind': 'FUNCTION' if not is_action else 'ACTION',
             'params': params_info,
             'return_type': return_z_type
        }
        # Declare in the parent scope (global) before we exit function scope
        parent_scope = symbol_table.scopes[-2]
        parent_scope[func_name.upper()] = {'name': func_name, 'z_type': func_info, 'c_type': return_c_type}


        # Generate C function signature
        params_c_str = ", ".join(params_c_parts) if params_c_parts else "void"
        signature = f"{return_c_type} {func_name}({params_c_str})"
        self.add_code(signature + " {", section="functions", indent=0)

        # Parse function body
        self.current_section = "functions"
        self.indent_level = 1
        self.parse_block() # Parse statements into the function body
        self.indent_level = 0
        self.add_code("}", section="functions", indent=0)
        self.add_code("", section="functions", indent=0) # Add blank line

        # Restore state
        self.current_section = "main" # Or whatever context called this
        self.indent_level = 1 # Reset indent? Context dependent.
        self.function_return_type = None
        symbol_table.exit_scope()

        self.expect('END')


    def parse_structure_definition(self):
        """ Parses STRUCTURE Name { Field1: Type; Field2: Type } """
        # STRUCTURE consumed
        struct_name = self.expect('IDENTIFIER').value
        uname = struct_name.upper()
        is_dynamic = self.consume_optional('DYNAMIC') # Check for DYNAMIC keyword? Not in grammar.

        # C names
        c_struct_tag = f"{struct_name}_t" # e.g., Personne_t
        c_typedef = struct_name # User-facing typedef name, e.g., Personne
        c_ptr_typedef = f"{struct_name}Ptr" # e.g., PersonnePtr

        fields = []
        # Use {} or BEGIN/END? Grammar has {}, templates use {}. Assume {}.
        self.expect('LBRACE')

        i = 1 # Field index for templates
        while not self.consume_optional('RBRACE'):
             field_name = self.expect('IDENTIFIER').value
             self.expect('COLON')
             field_z_type = self.parse_type()
             field_c_type = ztype_to_ctype(field_z_type)
             fields.append({
                 'name': field_name,
                 'z_type': field_z_type,
                 'c_type': field_c_type,
                 'index': i
             })
             self.consume_optional('SEMICOLON') # Optional semicolons between fields?
             i += 1

        # Store type definition
        struct_info = {
             'kind': 'STRUCTURE',
             'name': struct_name,
             'c_struct_name': c_struct_tag,
             'c_typedef': c_typedef,
             'c_ptr_typedef': c_ptr_typedef,
             'fields': fields,
             'dynamic': is_dynamic # TODO: Use this flag
        }
        type_definitions[uname] = struct_info


        # --- Generate C code using templates ---
        # 1. Struct definition
        self.add_code(f"// Structure Definition: {struct_name}", section="typedefs", indent=0)
        self.add_code(f"struct {c_struct_tag} {{", section="typedefs", indent=0)
        for field in fields:
            self.add_code(f"    {field['c_type']} {field['name']};", section="typedefs", indent=0)
        self.add_code(f"}}; ", section="typedefs", indent=0)

        # 2. Typedefs
        self.add_code(f"typedef struct {c_struct_tag} {c_typedef};", section="typedefs", indent=0)
        self.add_code(f"typedef {c_typedef}* {c_ptr_typedef};", section="typedefs", indent=0)
        self.add_code("", section="typedefs", indent=0) # Blank line

        # 3. Accessor and Assignment functions (using templates)
        # Determine if static or dynamic template keys are needed
        template_prefix = "STRUCTURES_DYNAMIQUES" if is_dynamic else "STRUCTURES_STATIQUES"
        template_accessor = CODE_TEMPLATES.get(template_prefix + "_4", "") # Struct%I%_%Types%
        template_assign = CODE_TEMPLATES.get(template_prefix + "_5", "") # Aff_struct%I%_%Types%

        if template_accessor and template_assign:
             self.add_code(f"// Accessors/Assigners for {struct_name}", section="functions", indent=0)
             for field in fields:
                  # Accessor
                  acc_code = template_accessor
                  acc_code = acc_code.replace('%I%', str(field['index']))
                  acc_code = acc_code.replace('%Types%', struct_name) # Z struct name
                  acc_code = acc_code.replace('%Pointeur%', c_ptr_typedef) # For dynamic ptr type
                  acc_code = acc_code.replace('Typestr_%Types%', c_ptr_typedef) # For static ptr type
                  acc_code = acc_code.replace('%Type_champI%', field['c_type']) # Replace return/param type
                  acc_code = acc_code.replace('Type%I%_%Types%', field['c_type']) # Alt placeholder name
                  acc_code = acc_code.replace('Champ%I%', field['name'])
                  self.add_code(acc_code, section="functions", indent=0)

                  # Assignment
                  aff_code = template_assign
                  aff_code = aff_code.replace('%I%', str(field['index']))
                  aff_code = aff_code.replace('%Types%', struct_name)
                  aff_code = aff_code.replace('%Pointeur%', c_ptr_typedef)
                  aff_code = aff_code.replace('Typestr_%Types%', c_ptr_typedef)
                  aff_code = aff_code.replace('%Type_champI%', field['c_type'])
                  aff_code = aff_code.replace('Type%I%_%Types%', field['c_type'])
                  aff_code = aff_code.replace('Champ%I%', field['name'])
                  # Basic $AFF replacement (simple assignment) - Needs improvement
                  aff_code = re.sub(r"(\$AFF|\$\$)|\/\*.*?\*\/\s*", "", aff_code) # Remove markers/comments
                  aff_code = aff_code.replace("=", "=", 1) # Ensure only one = remains if $$=$$ was used

                  # Handle potential memcpy for struct fields
                  if field['z_type']['kind'] in ['STRUCTURE_POINTER', 'ARRAY']: # Add other complex types
                       # Crude replacement assuming basic template structure
                       # Replace `S->Field = Val;` with memcpy
                       assign_regex = re.compile(rf"(\s*S->{field['name']}\s*=\s*Val\s*;)")
                       if assign_regex.search(aff_code):
                            aff_code = assign_regex.sub(f" memcpy(&S->{field['name']}, &Val, sizeof({field['c_type']}));", aff_code)
                       else: # Fallback if regex failed (e.g. template has different structure)
                            print(f"Warning: Could not apply memcpy for struct assign {struct_name}.{field['name']}", file=sys.stderr)


                  self.add_code(aff_code, section="functions", indent=0)
             self.add_code("", section="functions", indent=0) # Blank line

        # 4. Alloc/Liberer for dynamic structs
        if is_dynamic:
             alloc_tmpl = CODE_TEMPLATES.get("STRUCTURES_DYNAMIQUES_6", "") # Alloc_struct_%Types%
             free_tmpl = CODE_TEMPLATES.get("STRUCTURES_DYNAMIQUES_6_FREE", "") # Assumed key for Liber_struct
             if not free_tmpl: free_tmpl = CODE_TEMPLATES.get("STRUCTURES_DYNAMIQUES", "") # Find Liber_struct in general block

             if alloc_tmpl:
                  alloc_code = alloc_tmpl
                  alloc_code = alloc_code.replace('%Types%', struct_name)
                  alloc_code = alloc_code.replace('%Pointeur%', c_ptr_typedef)
                  alloc_code = alloc_code.replace('struct %Types%', c_typedef) # Use C typedef name
                  self.add_code(alloc_code, section="functions", indent=0)

             # Find Liber_struct_%Types% within the dynamic struct template block
             liber_match = re.search(r"void\s+Liber_struct_\w+\s*\(\s*\w+\s+\w+\s*\)\s*\{.*?\}", CODE_TEMPLATES.get("STRUCTURES_DYNAMIQUES",""), re.DOTALL)
             if liber_match:
                  free_code = liber_match.group(0)
                  free_code = free_code.replace('Liber_struct_%Types%', f'Liber_struct_{struct_name}')
                  free_code = free_code.replace('%Pointeur%', c_ptr_typedef)
                  self.add_code(free_code, section="functions", indent=0)
             self.add_code("", section="functions", indent=0)


    def parse_file_type_definition(self):
         """ Parses FILE TypeName { Fields... } HEADER { Fields... } """
         # FILE consumed
         file_type_name = self.expect('IDENTIFIER').value
         uname = file_type_name.upper()
         has_header = False
         record_fields = []
         header_fields = []

         # Parse Record fields
         self.expect('LBRACE') # Assuming record fields in {}
         i_rec = 1
         while self.current_token.type != 'RBRACE' and self.current_token.type != 'HEADER':
              field_name = self.expect('IDENTIFIER').value
              self.expect('COLON')
              field_z_type = self.parse_type()
              field_c_type = ztype_to_ctype(field_z_type)
              record_fields.append({'name': field_name, 'z_type': field_z_type, 'c_type': field_c_type, 'index': i_rec})
              self.consume_optional('SEMICOLON')
              i_rec += 1
         self.expect('RBRACE')

         # Parse Optional Header fields
         if self.consume_optional('HEADER'):
              has_header = True
              self.expect('LBRACE')
              i_head = 1
              while not self.consume_optional('RBRACE'):
                   field_name = self.expect('IDENTIFIER').value
                   self.expect('COLON')
                   field_z_type = self.parse_type()
                   field_c_type = ztype_to_ctype(field_z_type)
                   header_fields.append({'name': field_name, 'z_type': field_z_type, 'c_type': field_c_type, 'index': i_head})
                   self.consume_optional('SEMICOLON')
                   i_head += 1

         # Store type definition
         file_info = {
              'kind': 'FILE',
              'name': file_type_name,
              'has_header': has_header,
              'record_fields': record_fields,
              'header_fields': header_fields,
              'c_record_struct_name': f"Typestruct1_{file_type_name}_Buf", # From template Y
              'c_record_ptr_typedef': f"Typestruct1_{file_type_name}",    # From template Y
              'c_header_struct_name': f"Typestruct2_{file_type_name}" if has_header else None # From template Y
         }
         type_definitions[uname] = file_info

         # --- Generate C code using templates (Y or Q) ---
         template_key_prefix = "Y_FICHIERS_AVEC_ENTETE" if has_header else "Q_FICHIERS_SANS_ENTETE"
         file_template = CODE_TEMPLATES.get(template_key_prefix, "")
         if not file_template:
              raise ValueError(f"Could not find template block for key '{template_key_prefix}'")

         self.add_code(f"// --- File Type Definition: {file_type_name} ---", section="typedefs", indent=0)

         # Generate Record Struct (_Buf and pointer typedef)
         # Need to reconstruct from parts 0, 1, 3, 9 of templates Y/Q
         # Type definitions for each field
         for field in record_fields:
             # Template Y: 1typedef %Type_champI% Typechamp%I%_%Type_fichier%;
             # Template Q: 1typedef %Type_champI% Typechamp%I%_%Type_fichier%;
             td_code = f"typedef {field['c_type']} Typechamp{field['index']}_{file_type_name};"
             self.add_code(td_code, section="typedefs", indent=0)

         # Record struct _Buf definition
         # Template Y/Q: typedef struct { 0 Typechamp%I%_%Type_fichier% Champ%I% ; } Typestruct1_%Type_fichier%_Buf;
         self.add_code(f"typedef struct {{", section="typedefs", indent=0)
         for field in record_fields:
             self.add_code(f"    Typechamp{field['index']}_{file_type_name} {field['name']};", section="typedefs", indent=0)
         self.add_code(f"}} {file_info['c_record_struct_name']};", section="typedefs", indent=0)

         # Record struct pointer typedef
         # Template Y/Q: typedef Typestruct1_%Type_fichier%_ * Typestruct1_%Type_fichier% ; (assumes _ exists)
         # We defined the _Buf struct, so:
         self.add_code(f"typedef {file_info['c_record_struct_name']}* {file_info['c_record_ptr_typedef']};", section="typedefs", indent=0)

         # Generate Header Struct (only if has_header)
         if has_header:
             # Header field typedefs
             # Template Y: 2typedef %Type_enteteI% Typeentete%I%_%Type_fichier% ;
             for field in header_fields:
                  td_code = f"typedef {field['c_type']} Typeentete{field['index']}_{file_type_name};"
                  self.add_code(td_code, section="typedefs", indent=0)

             # Header struct definition
             # Template Y: typedef struct { 4 Typeentete%I%_%Type_fichier% Entete%I% ; } Typestruct2_%Type_fichier% ;
             self.add_code(f"typedef struct {{", section="typedefs", indent=0)
             for field in header_fields:
                  self.add_code(f"    Typeentete{field['index']}_{file_type_name} {field['name']};", section="typedefs", indent=0)
             self.add_code(f"}} {file_info['c_header_struct_name']};", section="typedefs", indent=0)

             # Global header buffer variable
             # Template Y: Typestruct2_%Type_fichier% Bloc_caract_%Type_fichier%;
             self.add_code(f"{file_info['c_header_struct_name']} Bloc_caract_{file_type_name};", section="globals", indent=0)

         self.add_code("", section="typedefs", indent=0) # Blank line

         # Generate functions (Ouvrir, Fermer, Lire, Ecrire, etc.)
         self.add_code(f"// --- File Operations: {file_type_name} ---", section="functions", indent=0)
         # Iterate through functions in the template block and perform replacements
         # This is complex because the template mixes definitions and functions.
         # Need to parse the template block more carefully.
         # Example for Ouvrir:
         ouvrir_match = re.search(r"void\s+Ouvrir_\w+\s*\(.*?\)\s*\{.*?\n\s*\}", file_template, re.DOTALL)
         if ouvrir_match:
             ouvrir_code = ouvrir_match.group(0)
             ouvrir_code = ouvrir_code.replace('Ouvrir_%Type_fichier%', f'Ouvrir_{file_type_name}')
             ouvrir_code = ouvrir_code.replace('%Type_fichier%', file_type_name) # Replace other placeholders
             # Handle $ lines (include or remove based on policy - include for now)
             ouvrir_code = ouvrir_code.replace('$', '') # Simple removal
             self.add_code(ouvrir_code, section="functions", indent=0)

         # Repeat for Fermer, Lireseq, Ecrireseq, Liredir, Ecriredir, Finfich, Alloc_bloc, Rajouter
         # And for header functions (Entete, Aff_entete) if has_header
         # And for record field accessors (Struct, Aff_struct)
         # --> This requires parsing the whole template block and doing replacements function by function.
         # --> This prototype skips the complex template parsing for brevity. A real implementation needs it.
         print(f"// TODO: Implement full function generation for file type {file_type_name}", file=sys.stderr)


    # --- Code Assembly ---
    def assemble_c_code(self):
        """Combines all generated C code parts into the final string."""
        final_code = []
        # Order: Includes, Macros, Typedefs, Globals, Functions, Main
        final_code.extend(sorted(list(self.c_code_parts["includes"])))
        if self.c_code_parts["macros"]:
            final_code.append("\n// --- Macros ---")
            final_code.extend(self.c_code_parts["macros"])
        if self.c_code_parts["typedefs"]:
            final_code.append("\n// --- Type Definitions ---")
            final_code.extend(self.c_code_parts["typedefs"])
        if self.c_code_parts["globals"]:
            final_code.append("\n// --- Global Declarations ---")
            final_code.extend(self.c_code_parts["globals"])
        if self.c_code_parts["functions"]:
            final_code.append("\n// --- Helper Functions / Actions ---")
            final_code.extend(self.c_code_parts["functions"])

        final_code.append("\n// --- Main Program ---")
        final_code.append("int main(int argc, char *argv[]) {")
        final_code.extend(self.c_code_parts["main"])
        final_code.append("    return 0;")
        final_code.append("}")
        return "\n".join(final_code)


# --- Main Execution ---
# --- Main Execution ---
if __name__ == "__main__":
    print("--- Script Started ---")
    print(f"Current Working Directory: {os.getcwd()}") # Print where the script thinks it is

    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(f"Usage: python {os.path.basename(__file__)} <input_z_file.alg> [output_c_file.c]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) == 3 else os.path.splitext(input_file)[0] + ".c"
    exe_name = os.path.splitext(output_file)[0]

    print(f"Input file: {input_file}")
    print(f"Output file: {output_file}")
    print(f"Template file variable: {TEMPLATE_FILE}") # Name the script uses
    template_full_path = os.path.abspath(TEMPLATE_FILE) # Get absolute path
    print(f"Attempting to load template from absolute path: {template_full_path}") # Print full path

    # --- FOCUSED DEBUGGING FOR TEMPLATE LOADING ---
    try:
        print("--- Checking if template file exists... ---")
        if not os.path.exists(template_full_path):
             print(f"--- ERROR: Template file NOT FOUND at '{template_full_path}' ---", file=sys.stderr)
             print("--- Please ensure 'z_templates.txt' is in the same directory as the script and spelled correctly. ---", file=sys.stderr)
             sys.exit(1)
        else:
             print(f"--- OK: Template file exists at '{template_full_path}' ---")

        print("--- Checking template file read permissions... ---")
        if not os.access(template_full_path, os.R_OK):
             print(f"--- ERROR: Cannot READ template file at '{template_full_path}' ---", file=sys.stderr)
             print("--- Please check the file permissions for 'z_templates.txt'. ---", file=sys.stderr)
             sys.exit(1)
        else:
             print(f"--- OK: Read permissions seem correct for template file ---")

        print("--- Attempting to load templates using load_templates_from_file... ---")
        # Pass the relative filename expected by the function
        CODE_TEMPLATES = load_templates_from_file(TEMPLATE_FILE)
        if not CODE_TEMPLATES:
            # load_templates_from_file already prints specific errors like FileNotFoundError
            # This catches if it returns empty for other reasons (e.g., bad format)
            print("--- ERROR: load_templates_from_file returned empty. Check file format (starts with *** KEY ***). ---", file=sys.stderr)
            sys.exit(1)
        print(f"--- Templates Loaded Successfully ({len(CODE_TEMPLATES)} found) ---")

    except Exception as e:
        # Catch any unexpected error during the loading process specifically
        print(f"\n--- UNEXPECTED ERROR during template loading phase ---", file=sys.stderr)
        traceback.print_exc() # Print detailed exception info
        print(f"----------------------------------------------------", file=sys.stderr)
        sys.exit(1)
    # --- END OF FOCUSED DEBUGGING ---


    # --- [Rest of the script continues below] ---
    try:
        if not os.path.exists(RUNTIME_SOURCE) or not os.path.exists(RUNTIME_HEADER):
             print(f"Warning: Runtime files '{RUNTIME_SOURCE}' or '{RUNTIME_HEADER}' not found.", file=sys.stderr)
             # Continue anyway, as only compilation needs them

        print(f"--- Reading Z code from: {input_file} ---")
        with open(input_file, 'r', encoding='utf-8') as f:
            z_code = f.read()
        print("--- Z Code Read Successfully ---")

        print("--- Tokenizing ---")
        tokens = list(tokenize(z_code))
        print(f"--- Tokenizing Complete ({len(tokens)} tokens) ---")

        print("--- Transpiling to C ---")
        transpiler = Transpiler(tokens)
        c_code = transpiler.parse()
        print("--- Transpiling Complete ---")

        print(f"--- Writing C code to: {output_file} ---")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(c_code)
        print("--- C Code Written Successfully ---")

        print("-" * 20)
        print(f"Successfully transpiled '{input_file}' to '{output_file}'")
        print("-" * 20)
        print("To compile the C code, run:")
        print(f"  gcc \"{output_file}\" \"{RUNTIME_SOURCE}\" -o \"{exe_name}\" -lm")
        print("-" * 20)

    except (RuntimeError, SyntaxError, TypeError, NameError, NotImplementedError, ValueError) as e:
        print(f"\n--- Transpilation Error ---", file=sys.stderr)
        print(f"Error: {e}", file=sys.stderr)
        # Attempt to provide more context if available from the exception or current state
        # current_line = transpiler.current_token.line if hasattr(transpiler, 'current_token') and transpiler.current_token else 'N/A'
        # print(f"(Approximate location near line: {current_line})", file=sys.stderr)
        print(f"---------------------------", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        # This specifically catches if the Z input file is not found
        print(f"--- ERROR: Input Z file '{input_file}' not found. ---", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
         print(f"\n--- An unexpected error occurred during core transpilation ---", file=sys.stderr)
         traceback.print_exc()
         print(f"-------------------------------------------------------------", file=sys.stderr)
         sys.exit(1)

    print("--- Script Finished ---")