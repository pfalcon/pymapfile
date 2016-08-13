WORKAROUND_XTENSA_LITERAL = 1


class GnuMapFile:

    def __init__(self, f):
        self.f = f
        self.l = None
        self.section_order = []
        self.sections = {}

    def get(self):
        if self.l is not None:
            l = self.l
            self.l = None
            return l
        return next(self.f)

    def unget(self, l):
        assert self.l is None
        self.l = l

    def peek(self):
        if self.l is None:
            self.l = next(self.f)
        return self.l

    def skip_till_memmap(self):
        for l in self.f:
            if l == "Linker script and memory map\n":
                break

    def skip_while_lead_space(self):
        while 1:
            if self.l is not None and self.l[0] not in [" ", "\n"]:
                break
            self.l = next(self.f)


    def parse_section_line(self):
        l = self.get().rstrip()
        if l[1] == " " and l[46] != " ":
            fields = l.split(None, 2)
            fields = [""] + fields
        else:
            fields = l.split()
            if len(fields) == 1:
                # For long section names, continuation on 2nd line
                fields2 = self.get().split()
                fields += fields2

        return [fields[0], int(fields[1], 0), int(fields[2], 0)] + fields[3:]

    def parse_section(self):
        sec_name, addr, sz = self.parse_section_line()
        if sz == 0:
            #logging.debug("Empty section: %s", sec_name)
            self.skip_while_lead_space()
            return

#        print(sec_name, addr, sz)
        self.section_order.append((sec_name, addr, sz))
        self.sections[sec_name] = {"addr": addr, "size": sz}

        last_obj = None
        while 1:
            l = self.get()
            if l == "\n":
                break

            if len(l) > 16 and l[16] == " ":
                assert "(size before relaxing)" in l
                continue

            if l[1] == " " and l[46] == " ":
                addr, sym = l.split(None, 1)
#                print((addr, sym))
                if " = " in sym:
                    # special symbol, like ABSOLUTE, ALIGN, etc.
                    continue
                self.sections[sec_name]["objects"][-1][-1].append((int(addr, 0), sym.rstrip()))
                continue

            if l.startswith(" *fill* "):
                self.unget(l)
                fields = self.parse_section_line()
                if fields[2] == 0:
                    continue
                if last_obj is None:
                    name = sec_name + ".initial_align"
                else:
                    name = last_obj + ".fill"
                self.sections[sec_name].setdefault("objects", []).append(fields + [name, []])
                continue

            if l.startswith(" *"):
                # section group "comment"
                continue
#            print("*", l)

            self.unget(l)
            fields = self.parse_section_line()
            if fields[2] == 0:
                if WORKAROUND_XTENSA_LITERAL:
                    # Empty *.literal sub-section followed by
                    # non-empty fill is actually non-empty *.literal
                    if fields[0].endswith(".literal"):
                        if self.peek().startswith(" *fill* "):
                            fields2 = self.parse_section_line()
                            if fields2[2] != 0:
#                                assert 0, (fields, fields2)
                                fields[2] = fields2[2]
                                fields[-1] += ".literal"
                                self.sections[sec_name].setdefault("objects", []).append(fields + [[]])
                continue

            # If an absolute library name (libc, etc.), use the last component
            if fields[-1][0] == "/":
                fields[-1] = fields[-1].rsplit("/", 1)[1]

            self.sections[sec_name].setdefault("objects", []).append(fields + [[]])
            last_obj = fields[-1]
#            assert 0, fields

    def parse_sections(self):
        while 1:
            l = self.peek()
            if l.startswith("LOAD ") and len(l.split()) == 2:
                break
            self.parse_section()

    # Validate that all sub-sections are adjacent (and thus don't overlap),
    # and fill in parent section completely. Note that read-only string
    # section may be subject of string merging optimization by linker,
    # and fail adjacency check. To "fix" this, "M" flag on ELF section
    # should be unset (e.g. with objcopy --set-section-flags)
    def validate(self):
        for k, sec_addr, sec_sz in self.section_order:
            next_addr = sec_addr
            for sec, addr, sz, obj, symbols in self.sections[k]["objects"]:
                if addr != next_addr:
                    print("%x vs %x" % (addr, next_addr))
                    next_addr = addr
                next_addr += sz
            assert next_addr == sec_addr + sec_sz, "%x vs %x" % (next_addr, sec_addr + sec_sz)
