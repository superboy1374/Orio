#-----------------------------------------------------------------
# _ast_gen.py
#
# Generates the AST Node classes from a specification given in 
# a .yaml file
#
# The design of this module was inspired by astgen.py from the
# Python 2.5 code-base.
#
# Copyright (C) 2008-2011, Eli Bendersky
# License: BSD
#-----------------------------------------------------------------
import pprint
from string import Template


class ASTCodeGenerator(object):
    def __init__(self, cfg_filename='_c_ast.cfg'):
        """ Initialize the code generator from a configuration
            file.
        """
        self.cfg_filename = cfg_filename
        self.node_cfg = [NodeCfg(name, contents) for (name, contents) in self.parse_cfgfile(cfg_filename)]

    def generate(self, file=None):
        """ Generates the code into file, an open file buffer.
        """
        src = Template(_PROLOGUE_COMMENT).substitute(
            cfg_filename=self.cfg_filename)
        
        src += _PROLOGUE_CODE
        for node_cfg in self.node_cfg:
            src += node_cfg.generate_source() + '\n\n'
        
        file.write(src)

    def parse_cfgfile(self, filename):
        """ Parse the configuration file and yield pairs of
            (name, contents) for each node.
        """
        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                colon_i = line.find(':')
                lbracket_i = line.find('[')
                rbracket_i = line.find(']')
                if colon_i < 1 or lbracket_i <= colon_i or rbracket_i <= lbracket_i:
                    raise RuntimeError("Invalid line in %s:\n%s\n" % (filename, line))

                name = line[:colon_i]
                val = line[lbracket_i + 1:rbracket_i]
                vallist = [v.strip() for v in val.split(',')] if val else []
                yield name, vallist


class NodeCfg(object):
    """ Node configuration. 

        name: node name
        contents: a list of contents - attributes and child nodes 
        See comment at the top of the configuration file for details.
    """
    def __init__(self, name, contents):
        self.name = name
        self.all_entries = []
        self.attr = []
        self.child = []
        self.seq_child = []

        for entry in contents:
            clean_entry = entry.rstrip('*')
            self.all_entries.append(clean_entry)
            
            if entry.endswith('**'):
                self.seq_child.append(clean_entry)
            elif entry.endswith('*'):
                self.child.append(clean_entry)
            else:
                self.attr.append(entry)

    def generate_source(self):
        src = self._gen_init()
        src += '\n' + self._gen_children()
        src += '\n' + self._gen_show()
        return src
    
    def _gen_init(self):
        src = "class %s(Node):\n" % self.name

        if self.all_entries:
            args = ', '.join(self.all_entries)
            arglist = '(self, %s, coord=None)' % args
        else:
            arglist = '(self, coord=None)'
        
        src += "    def __init__%s:\n" % arglist
        
        for name in self.all_entries + ['coord']:
            src += "        self.%s = %s\n" % (name, name)
        
        return src
    
    def _gen_children(self):
        src = '    def children(self):\n'
        
        if self.all_entries:
            src += '        nodelist = []\n'
            
            template = ('' +
                '        if self.%s is not None:' +
                ' nodelist.%s(self.%s)\n')
            
            for child in self.child:
                src += template % (
                    child, 'append', child)
            
            for seq_child in self.seq_child:
                src += template % (
                    seq_child, 'extend', seq_child)
                    
            src += '        return tuple(nodelist)\n'
        else:
            src += '        return ()\n'
            
        return src

    def _gen_show(self):
        src = "    attr_names = (" + ''.join("%r," % nm for nm in self.attr) + ')' 
        return src


_PROLOGUE_COMMENT = \
r'''#-----------------------------------------------------------------
# ** ATTENTION **
# This code was automatically generated from the file:
# $cfg_filename 
#
# Do not modify it directly. Modify the configuration file and
# run the generator again.
# ** ** *** ** **
#
# pycparser: c_ast.py
#
# AST Node classes.
#
# Copyright (C) 2008-2011, Eli Bendersky
# License: BSD
#-----------------------------------------------------------------

'''

_PROLOGUE_CODE = r'''
import sys


class Node(object):
    """ Abstract base class for AST nodes.
    """
    def children(self):
        """ A sequence of all children that are Nodes
        """
        pass

    def show(self, buf=sys.stdout, offset=0, attrnames=False, showcoord=False):
        """ Pretty print the Node and all its attributes and
            children (recursively) to a buffer.
            
            file:   
                Open IO buffer into which the Node is printed.
            
            offset: 
                Initial offset (amount of leading spaces) 
            
            attrnames:
                True if you want to see the attribute names in
                name=value pairs. False to only see the values.
            
            showcoord:
                Do you want the coordinates of each Node to be
                displayed.
        """
        lead = ' ' * offset
        buf.write(lead + self.__class__.__name__+': ')

        if self.attr_names:
            if attrnames:
                nvlist = [(n, getattr(self,n)) for n in self.attr_names]
                attrstr = ', '.join('%s=%s' % nv for nv in nvlist)
            else:
                vlist = [getattr(self, n) for n in self.attr_names]
                attrstr = ', '.join('%s' % v for v in vlist)
            buf.write(attrstr)

        if showcoord:
            buf.write(' (at %s)' % self.coord)
        buf.write('\n')

        for c in self.children():
            c.show(buf, offset + 2, attrnames, showcoord)


class NodeVisitor(object):
    """ A base NodeVisitor class for visiting c_ast nodes. 
        Subclass it and define your own visit_XXX methods, where
        XXX is the class name you want to visit with these 
        methods.
        
        For example:
        
        class ConstantVisitor(NodeVisitor):
            def __init__(self):
                self.values = []
            
            def visit_Constant(self, node):
                self.values.append(node.value)

        Creates a list of values of all the constant nodes 
        encountered below the given node. To use it:
        
        cv = ConstantVisitor()
        cv.visit(node)
        
        Notes:
        
        *   generic_visit() will be called for AST nodes for which 
            no visit_XXX method was defined. 
        *   The children of nodes for which a visit_XXX was 
            defined will not be visited - if you need this, call
            generic_visit() on the node. 
            You can use:
                NodeVisitor.generic_visit(self, node)
        *   Modeled after Python's own AST visiting facilities
            (the ast module of Python 3.0)
    """
    def visit(self, node):
        """ Visit a node. 
        """
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        return visitor(node)
        
    def generic_visit(self, node):
        """ Called if no explicit visitor function exists for a 
            node. Implements preorder visiting of the node.
        """
        for c in node.children():
            self.visit(c)


'''


if __name__ == "__main__":
    import sys
    ast_gen = ASTCodeGenerator('_matrix_ast.cfg')
    ast_gen.generate(open('matrix_ast.py', 'w'))

