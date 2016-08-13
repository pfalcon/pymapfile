#
# Parse mapfile and dump all information collected.
#
import sys
import logging
from pprint import pprint

from mapfile import GnuMapFile


logging.basicConfig(level=logging.DEBUG)

f = open(sys.argv[1])
m = GnuMapFile(f)
m.skip_till_memmap()
m.skip_while_lead_space()
m.parse_sections()
m.validate()

#pprint(m.sections)
for k, addr, sz in m.section_order:
    print("%08x %08x %s" % (addr, sz, k))
    for sec, addr, sz, obj, symbols in m.sections[k]["objects"]:
        print(" %08x %08x %s" % (addr, sz, obj))
        for addr, sym in symbols:
            print("  %08x %s" % (addr, sym))
    print()
