# This script generates the opcode.h header file.

import sys
import tokenize

header = """
/* Auto-generated by Tools/scripts/generate_opcode_h.py from Lib/opcode.py */
#ifndef Py_OPCODE_H
#define Py_OPCODE_H
#ifdef __cplusplus
extern "C" {
#endif


/* Instruction opcodes for compiled code */
""".lstrip()

footer = """
#define HAS_ARG(op) ((op) >= HAVE_ARGUMENT)

/* Reserve some bytecodes for internal use in the compiler.
 * The value of 240 is arbitrary. */
#define IS_ARTIFICIAL(op) ((op) > 240)

#ifdef __cplusplus
}
#endif
#endif /* !Py_OPCODE_H */
"""

DEFINE = "#define {:<38} {:>3}\n"

UINT32_MASK = (1<<32)-1

def write_int_array_from_ops(name, ops, out):
    bits = 0
    for op in ops:
        bits |= 1<<op
    out.write(f"static const uint32_t {name}[8] = {{\n")
    for i in range(8):
        out.write(f"    {bits & UINT32_MASK}U,\n")
        bits >>= 32
    assert bits == 0
    out.write(f"}};\n")

def main(opcode_py, outfile='Include/opcode.h'):
    opcode = {}
    if hasattr(tokenize, 'open'):
        fp = tokenize.open(opcode_py)   # Python 3.2+
    else:
        fp = open(opcode_py)            # Python 2.7
    with fp:
        code = fp.read()
    exec(code, opcode)
    opmap = opcode['opmap']
    opname = opcode['opname']
    hasconst = opcode['hasconst']
    hasjrel = opcode['hasjrel']
    hasjabs = opcode['hasjabs']
    used = [ False ] * 256
    next_op = 1

    for name, op in opmap.items():
        used[op] = True

    specialized_opmap = {}
    opname_including_specialized = opname.copy()
    for name in opcode['_specialized_instructions']:
        while used[next_op]:
            next_op += 1
        specialized_opmap[name] = next_op
        opname_including_specialized[next_op] = name
        used[next_op] = True
    specialized_opmap['DO_TRACING'] = 255
    opname_including_specialized[255] = 'DO_TRACING'
    used[255] = True

    with open(outfile, 'w') as fobj:
        fobj.write(header)
        for name in opname:
            if name in opmap:
                fobj.write(DEFINE.format(name, opmap[name]))
            if name == 'POP_EXCEPT': # Special entry for HAVE_ARGUMENT
                fobj.write(DEFINE.format("HAVE_ARGUMENT", opcode["HAVE_ARGUMENT"]))

        for name, op in specialized_opmap.items():
            fobj.write(DEFINE.format(name, op))

        fobj.write("\nextern const uint8_t _PyOpcode_Caches[256];\n")
        fobj.write("\nextern const uint8_t _PyOpcode_Deopt[256];\n")
        fobj.write("\n#ifdef NEED_OPCODE_TABLES\n")
        write_int_array_from_ops("_PyOpcode_RelativeJump", opcode['hasjrel'], fobj)
        write_int_array_from_ops("_PyOpcode_Jump", opcode['hasjrel'] + opcode['hasjabs'], fobj)

        fobj.write("\nconst uint8_t _PyOpcode_Caches[256] = {\n")
        for i, entries in enumerate(opcode["_inline_cache_entries"]):
            if entries:
                fobj.write(f"    [{opname[i]}] = {entries},\n")
        fobj.write("};\n")
        deoptcodes = {}
        for basic in opmap:
            deoptcodes[basic] = basic
        for basic, family in opcode["_specializations"].items():
            for specialized in family:
                deoptcodes[specialized] = basic
        fobj.write("\nconst uint8_t _PyOpcode_Deopt[256] = {\n")
        for opt, deopt in sorted(deoptcodes.items()):
            fobj.write(f"    [{opt}] = {deopt},\n")
        fobj.write("};\n")
        fobj.write("#endif /* OPCODE_TABLES */\n")

        fobj.write("\n")
        fobj.write("#define HAS_CONST(op) (false\\")
        for op in hasconst:
            fobj.write(f"\n    || ((op) == {op}) \\")
        fobj.write("\n    )\n")

        fobj.write("\n")
        for i, (op, _) in enumerate(opcode["_nb_ops"]):
            fobj.write(DEFINE.format(op, i))

        fobj.write("\n")
        fobj.write("#ifdef Py_DEBUG\n")
        fobj.write("static const char *const _PyOpcode_OpName[256] = {\n")
        for op, name in enumerate(opname_including_specialized):
            if name[0] != "<":
                op = name
            fobj.write(f'''    [{op}] = "{name}",\n''')
        fobj.write("};\n")
        fobj.write("#endif\n")

        fobj.write(footer)


    print(f"{outfile} regenerated from {opcode_py}")


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
