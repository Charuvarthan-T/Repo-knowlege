import os
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser


def get_parser_for_file(file_path):
    """Get the appropriate parser based on file extension"""
    if file_path.endswith('.py'):
        language = Language(tspython.language())
        return Parser(language), 'python'
    elif file_path.endswith('.js') or file_path.endswith('.jsx'):
        language = Language(tsjs.language())
        return Parser(language), 'javascript'
    elif file_path.endswith('.ts'):
        language = Language(tsts.language_typescript())
        return Parser(language), 'typescript'
    elif file_path.endswith('.tsx'):
        language = Language(tsts.language_tsx())
        return Parser(language), 'typescript'
    return None, None


def find_docstrings_recursively(node, language_type='python'):
    """Find documentation strings/comments for multiple languages"""
    docstrings = {}
    
    # Language-specific function definition patterns
    function_types = {
        'python': ['function_definition'],
        'javascript': ['function_declaration', 'arrow_function', 'method_definition'],
        'typescript': ['function_declaration', 'arrow_function', 'method_definition', 'function_signature']
    }
    
    if node.type in function_types.get(language_type, []):
        func_name = extract_function_name(node, language_type)
        if func_name:
            docstring = extract_documentation(node, language_type)
            if docstring:
                docstrings[func_name] = docstring
    
    for child in node.children:
        child_docstrings = find_docstrings_recursively(child, language_type)
        docstrings.update(child_docstrings)
            
    return docstrings


def extract_function_name(node, language_type):
    """Extract function name based on language type"""
    if language_type == 'python':
        name_node = node.child_by_field_name('name')
        return name_node.text.decode('utf8') if name_node else None
    
    elif language_type in ['javascript', 'typescript']:
        if node.type == 'function_declaration':
            name_node = node.child_by_field_name('name')
            return name_node.text.decode('utf8') if name_node else None
        elif node.type == 'method_definition':
            name_node = node.child_by_field_name('name')
            return name_node.text.decode('utf8') if name_node else None
        elif node.type == 'arrow_function':
            # For arrow functions, we'd need to look at the assignment
            return None
    
    return None


def extract_documentation(node, language_type):
    """Extract documentation based on language type"""
    if language_type == 'python':
        # Python docstrings
        func_body_node = node.child_by_field_name('body')
        if func_body_node and func_body_node.children:
            first_child = func_body_node.children[0]
            if first_child and first_child.type == 'expression_statement':
                string_node = first_child.children[0] if first_child.children else None
                if string_node and string_node.type == 'string':
                    docstring_text = string_node.text.decode('utf8').strip().strip('"""').strip("'''")
                    return docstring_text if docstring_text else None
    
    elif language_type in ['javascript', 'typescript']:
        # Look for JSDoc comments before the function
        # Find the previous sibling that might be a comment
        parent = node.parent
        if parent:
            node_index = parent.children.index(node)
            if node_index > 0:
                prev_node = parent.children[node_index - 1]
                if prev_node.type == 'comment':
                    comment_text = prev_node.text.decode('utf8')
                    # Clean up JSDoc comment
                    if comment_text.startswith('/**') and comment_text.endswith('*/'):
                        # Remove /** */ and clean up
                        cleaned = comment_text[3:-2].strip()
                        lines = [line.strip().lstrip('*').strip() for line in cleaned.split('\n')]
                        return '\n'.join(lines).strip()
                    elif comment_text.startswith('//'):
                        # Single line comment
                        return comment_text[2:].strip()
    
    return None