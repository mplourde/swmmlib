import re 
import sys
import os
import copy
import hashlib
import inspect
import linecache
import datetime
import itertools
import traceback, code
import StringIO
from operator import itemgetter
from collections import OrderedDict

# TODO : serialize supporting files in temp directory to prevent large files crowding memory

def get_element_classes(inp_path=None, long_line_comment=False, require_support_files=False):

    class ElementClass(object):
        def __init__(self):
            self.elements = []
            self.name_field = 'Name'
            self.desc_field = 'Description'
            self.ordinal_field = None
            self.md5_field = None
            self.subclasses = {}
            self.composite_class = None
            self.composite_name = []
            self.defaults = {}
            self.inp_grouping = None
            self.sort_by = [self.name_field]

        def as_xml(self):
            elements = self.get_elements()
            if len(elements) > 0:
                xml_str = '\t<' + self.section + '>\n'
                for element in elements:
                    xml_str += '\t\t<Element>\n'
                    for parameter, value in element.items():
                        if value is None:
                            value = 'NULL'
                        elif isinstance(value, str): 
                            if re.search('Description', parameter):
                                pass
                                #value = value.encode('string-escape')
                            else:
                                value = value.replace("\n", "\\n")
                            value = value.replace('&', '&amp;')
                            value = value.replace('"', '&quot;')
                            value = value.replace('<', '&lt;')
                            value = value.replace('>', '&gt;')
                            value = value.replace("'", '&apos;')
                            value = value.replace("\x92", "'") # replace foot mark with apostrophe
                            non_ascii = [ch for ch in value if ord(ch) >= 128]
                            if len(non_ascii) != 0:
                                exc = 'Non-ascii values ' + str(non_ascii) + ' in ' + section + \
                                    ' for parameter ' + parameter + '.'
                                raise Exception(exc)
                        xml_str += '\t\t\t<' + parameter + '>' + str(value) + '</' + parameter + '>\n'
                    xml_str += '\t\t</Element>\n'
                xml_str += '\t</' + self.section + '>\n'
                return xml_str
            else:
                return ''

        def assign(self, subclass):
            if self.elements:
                if subclass.section not in self.subclasses.keys():
                    raise Exception(subclass.section + " is not a valid subclass of " + self.section)
                if subclass.desc_field == self.desc_field:
                    sub_desc_field = subclass.section + 'Description'
                else:
                    sub_desc_field = subclass.desc_field

                self.defaults = dict(self.defaults.items() + subclass.defaults.items())
                subfields = subclass.fields.keys()
                subfields.remove(subclass.name_field)

                if not len(subclass.elements) and self.subclasses[subclass.section]:
                    exc = "assign: There are no elements in " + subclass.inp_label + " to assign to " + self.inp_label
                    raise Exception(exc)
                else:
                    for element in self.elements:
                        name = element[self.name_field]
                        subclass_has_element = False
                        for subelement in subclass.elements:
                            if subclass.section == 'Tags':
                                tag_condition = subelement['TagType'] == self.tag_type
                            else:
                                tag_condition = True

                            if name == subelement[subclass.name_field] and tag_condition:
                                for field in subfields:
                                    try:
                                        element[field] = subelement[field]
                                    except KeyError:
                                        element[field] = subclass.defaults[field]

                                if sub_desc_field:
                                    element[sub_desc_field] = subelement[subclass.desc_field]
                                subclass_has_element = True
                                break

                        if not subclass_has_element:
                            if self.subclasses[subclass.section]:
                                exc = "No entry in " + subclass.inp_label + " for " + name + " in " + self.inp_label
                                raise Exception(exc)
                            else:
                                if not hasattr(subclass, 'defaults'):
                                    exc = "There are no default elements for " + subclass.inp_label + \
                                          " to assign to " + name + " in " + self.inp_label
                                    raise Exception(exc)

                                for field in subfields:
                                    if field not in subclass.defaults.keys():
                                        raise Exception(subclass.section + " is missing a default for the field " + field)
                                    element[field] = subclass.defaults[field]

                                if sub_desc_field:
                                    element[sub_desc_field] = ''

    class INPElementClass(ElementClass):
        def __init__(self, start_lineno=None, end_lineno=None):
            ElementClass.__init__(self)
            self.inp_path = inp_path
            self.pats = {'header'            : re.compile('^[\s]*\;\;'), 
                         'blank_or_tag'      : re.compile('^([\s]*\[)|([\s]*$)'),
                         'desc'              : re.compile('^[\s]*\;'),
                         'adj_semicolons'    : re.compile('[ ;]*;'),
                         'semicolon'         : re.compile(';'),
                         'desc_whitespace'   : '; \t\n',
                        }
            if start_lineno is not None and end_lineno is not None:
                self.long_line_comment = long_line_comment
                self.require_support_files = require_support_files
                self.start_lineno = start_lineno
                self.end_lineno = end_lineno

        def get_elements(self):
            return self.elements

        def add_elements(self, elements, ignore_fields=[]):
            ignore_fields = ignore_fields + [self.desc_field, self.ordinal_field, self.name_field]
            for element in elements:
                e = dict((field, element[field]) for field in self.fields.keys())
                
                if all([e[name] is None for name in self.fields.keys() if name not in ignore_fields]):
                    continue

                if self.name_field and self.name_field not in self.fields.keys():
                    e[self.name_field] = element[self.name_field]

                if self.ordinal_field and self.ordinal_field not in self.fields.keys():
                    e[self.ordinal_field] = element[self.ordinal_field]

                if self.desc_field:
                    e[self.desc_field] = element[self.desc_field]

                if self.md5_field:
                    e[self.md5_field] = element[self.md5_field]

                self.elements.append(e)

        def get_elements(self):
            return self.elements

        def _ambiguous_line_exc(self, line):
            msg =  ': Ambiguous line encountered. This section does not support unmarked end of line descriptions.'
            return Exception(self.section + msg + '\n' + str(line))

        def _unexpected_line_exc(self, line):
            return Exception(self.section + ': Unexpected line format encountered.' + '\n' + str(line))

        def _missing_file_exc(self, filepath):
            return Exception('Cannot find support file ' + filepath + ' referenced in ' + self.section)

        def getline(self, i):
            if self.inp_path:
                return re.sub('\\xa0', ' ', linecache.getline(self.inp_path, i))
            else:
                raise Exception("Can't retrieve line, no file identified.")

        def parse(self):
            element_desc = ''
            past_header = False
                
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if (re.match(self.pats['header'], line) and not past_header) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    past_header = True
                    if re.match(self.pats['desc'], line):
                        desc = line.strip(self.pats['desc_whitespace'])
                        element_desc = desc if not element_desc else '\n'.join([element_desc, desc])
                        continue
                    else:
                        line_descs = {'marked' : '', 'unmarked' : ''}

                        if re.search(self.pats['semicolon'], line):
                            line, line_descs['marked'] = re.split(self.pats['adj_semicolons'], line, maxsplit=1)
                            line_descs['marked'] = line_descs['marked'].strip(self.pats['desc_whitespace'])

                        line, line_descs['unmarked'], file_md5 = self._parse_line(line)

                        if all(line_descs.values()):
                            line_desc = ' ; '.join([line_descs['unmarked'], line_descs['marked']])
                        elif line_descs['marked']:
                            line_desc = line_descs['marked']
                        elif line_descs['unmarked']:
                            line_desc = line_descs['unmarked']
                        else:
                            line_desc = ''

                        if line_desc:
                            element_desc = line_desc if not element_desc else '\n'.join([element_desc, line_desc])

                        line = [self.fields.values()[j](value) if value else value for j, value in enumerate(line)]
                        params = dict(zip(self.fields.keys(), line))
                        if self.composite_name:
                            params[self.name_field] = ':'.join([str(params[field]) for field in self.composite_name])

                        element_desc = element_desc.replace('\\n', '\n')

                        params[self.desc_field] = element_desc
                        if hasattr(self, 'files'):
                            params[self.md5_field] = file_md5

                        self.elements.append(params)
                        element_desc = ''

        def inp_lines(self, elements=None, fieldnames=None, exclude_descs=False, eol_descs=False):
            if elements is None:
                elements = self.elements

            if fieldnames is None:
                fieldnames = self.fields.keys()

            sort_by = self.sort_by + [self.ordinal_field] if self.ordinal_field else self.sort_by
            elements = sorted(elements, key=lambda x: tuple(x[name] for name in sort_by))

            if not elements:
                return []

            field_widths = {}
            data_widths = {}
            field_separator = ' '*3
            for name in fieldnames:
                width = max([len(str(row[name])) for row in elements] + [len(name)])
                field_widths[name] = width
                data_widths[name] = width + len(field_separator)

            field_fmt_strs = dict([(name, '{:<' + str(width) + '}') for name, width in field_widths.items()])
            data_fmt_strs = dict([(name, '{:<' + str(width) + '}') for name, width in data_widths.items()])

            section_exists = False
            inp_lines = [self.inp_label]
            fields_formatted = [field_fmt_strs[name].format(name) for name in fieldnames]
            fields_formatted = ';;' + field_separator.join(fields_formatted)
            inp_lines.append(fields_formatted)

            divider = ['-'*field_widths[name] for name in fieldnames]
            divider = ';;' + field_separator.join(divider)
            inp_lines.append(divider)

            prev_newline_field_value = None
            for i, e in enumerate(elements):
                if self.inp_grouping:
                    if not i:
                        prev_newline_field_value = e[self.inp_grouping]
                    if e[self.inp_grouping] != prev_newline_field_value:
                        inp_lines.append('')
                    prev_newline_field_value = e[self.inp_grouping]

                eol_description = ''
                if self.desc_field and not exclude_descs:
                    desc = e[self.desc_field]
                    if desc:
                        if not eol_descs:
                            #desc = desc.decode('string-escape').split('\n')
                            desc = desc.split('\n')
                            inp_lines.extend(['; ' + line for line in desc])
                        else:
                            #desc = desc.encode('string-escape')
                            desc = desc.replace('\n', '\\n') 
                            eol_description = ' '*4 + '; ' + desc

                formatted_row = []
                for name in fieldnames:
                    value = e[name]
                    if value is None:
                        value = ''
                    elif isinstance(value, float):
                        if value == int(value):
                            value = int(value)
                    value = str(value)
                    if len(value) >= data_widths[name] - 1:
                        value = value + '  '
                    formatted_row.append(data_fmt_strs[name].format(value))
                formatted_row[0] = formatted_row[0] + '  '
                formatted_row = ''.join(formatted_row) + eol_description
                inp_lines.append(formatted_row)

            return inp_lines

    class CompositeElementClass(ElementClass):
        def __init__(self, **kwargs):
            ElementClass.__init__(self)
            #args, _, _, values = inspect.getargvalues(inspect.currentframe())
            self.objects = kwargs
            self.desc_field = None
            desc_fields = []
            self.fields = OrderedDict([])

        def inp_lines(self, **kwargs):
            return reduce(lambda x,y: x + ['', ''] + y, [obj.inp_lines(**kwargs) for obj in self.objects.values()], [])[2:]

        def add_elements(self, elements):
            shared_names = []
            for i, obj in enumerate(self.objects.values()):
                shared_names = list(set(shared_names) & set(obj.fields.keys())) if i else obj.fields.keys()

            for name in self.objects.keys():
                self.objects[name].add_elements(elements, ignore_fields=shared_names)

        def get_elements(self):
            fields = OrderedDict()
            desc_fields = []
            defaults = {}
            for cls in self.objects.values():
                for name, value in cls.defaults.items():
                    if name not in defaults.keys():
                        defaults[name] = value
                if cls.desc_field in defaults.keys():
                    raise Exception("Components of a composite class can't have identical description fields.")
                defaults[cls.desc_field] = ''

            self.name_field = None

            def compose(total, next_cls):
                if not total:
                    total = copy.copy(next_cls.elements)
                    self.name_field = next_cls.name_field
                else:
                    name_field = next_cls.name_field

                    for next_el in next_cls.elements:
                        total_has_element = False
                        for existing_el in total:
                            if next_el[next_cls.name_field] == existing_el[self.name_field]:
                                fields = next_cls.fields.keys()
                                if next_cls.name_field in fields:
                                    fields.remove(next_cls.name_field)

                                for field in fields:
                                    if field in existing_el.keys():
                                        existing_val = existing_el[field]
                                        next_val = next_el[field]
                                        if existing_val != next_val:
                                            raise Exception("Cannot create composite element. ")

                                    existing_el[field] = next_el[field]

                                existing_el[next_cls.desc_field] = next_el[next_cls.desc_field]
                                total_has_element = True
                                break

                        if not total_has_element:
                            name = next_el[next_cls.name_field]
                            del next_el[next_cls.name_field]
                            next_el[self.name_field] = name
                            total.append(next_el)

                return total

            elements = reduce(compose, self.objects.values(), [])
            
            fieldnames = defaults.keys()
            for element in elements:
                element_fields = element.keys()
                for fieldname in fieldnames:
                    if fieldname not in element_fields:
                        element[fieldname] = defaults[fieldname]

            return elements

    class ElementClasses(object):
        def __init__(self):
            self.classes_by_label = OrderedDict()
            self.classes_by_name = OrderedDict()
            self.inp_path = inp_path
            self.meta_data = None
            
            self.objects = OrderedDict()

        def get_files(self):
            files = {}
            for obj in self.objects.values():
                if hasattr(obj, 'files'):
                    for path, md5 in obj.files.items():
                        files[path] = md5
            return files

        def get_supported_classes(self, by_name=True):
            return self.classes_by_name.keys() if by_name else self.classes_by_label.keys()

        def add_meta_data(self, data):
            self.meta_data = data


        def get_inp_text(self, exclude_descs=False, eol_descs=False):
            f = StringIO.StringIO('')
            if self.meta_data:
                meta_data = self.meta_data.split('\n') if isinstance(self.meta_data, str) else self.meta_data
                data = [line if line.strip().startswith(';') else ';; ' + line for line in meta_data]
                f.writelines('\n'.join(data) + '\n\n')

            objs = filter(lambda x: x.get_elements(), self.objects.values())
            for obj in sorted(objs, key=lambda x: self.classes_by_name.keys().index(x.section)):
                f.write('\n'.join(obj.inp_lines(exclude_descs=exclude_descs, eol_descs=eol_descs)) + '\n'*3)
            
            return f.getvalue()

        def write_inp(self, exclude_descs=False, eol_descs=False):
            if not self.inp_path:
                raise Exception("Can't write *.inp, no path defined.")

            inp_text = self.get_inp_text(exclude_descs=exclude_descs, eol_descs=eol_descs)
            with open(self.inp_path, 'w') as f:
                f.write(inp_text)

        def append(self, cls):
            if issubclass(cls, INPElementClass):
                min_lab = self.get_minimal_label(cls.inp_label)
                self.classes_by_label[min_lab] = cls

            self.classes_by_name[cls.__name__] = cls

            return cls

        def add_elements(self, name, elements, recognize_subclasses=False):
            if name in self.objects.keys():
                self.objects[name].add_elements(elements)
                obj = self.objects[name]
            else:
                obj = self.classes_by_name[name]()
                obj.add_elements(elements)
                self.objects[name] = obj

            if recognize_subclasses:
                for subclass_name in obj.subclasses.keys():
                    if subclass_name in self.objects.keys():
                        self.objects[subclass_name].add_elements(elements)
                    else:
                        subclass = self.classes_by_name[subclass_name]()
                        subclass.add_elements(elements)
                        self.objects[subclass_name] = subclass
                 
        def get_object_names(self):
            return self.objects.keys()

        def get_minimal_label(self, label):
            min_label_len = 5
            lbl = label.strip().lower()
            return lbl[:min(len(lbl), min_label_len)].strip(']')

        def initialize_class(self, label, start_lineno, end_lineno):
            min_label = self.get_minimal_label(label)
            if min_label not in self.classes_by_label.keys():
                raise Exception("Unrecognized INP label encountered: " + label.strip())
            else:
                cls = self.classes_by_label[min_label]
                obj = cls(start_lineno, end_lineno)
                self.objects[obj.section] = obj

        def merge_subclasses(self):
            subclasses_merged = []
            for name, obj in self.objects.items():
                if obj.subclasses:
                    for subclass_name, is_required in obj.subclasses.items():
                        if subclass_name not in self.objects.keys():
                            if is_required:
                                exc = "Cannot add subclass " + subclass_name + " to " + name + ". Subclass not found."
                                raise Exception(exc)
                            else:
                                subclass = self.classes_by_name[subclass_name]()
                        else:
                            subclass = self.objects[subclass_name]

                        self.objects[name].assign(subclass)
                        subclasses_merged.append(subclass_name)

            for name in list(set(subclasses_merged)):
                if name in self.objects.keys():
                    del self.objects[name]
        
        def merge_composite_classes(self):
            objs_merged = []
            key = lambda obj: obj.composite_class
            objs_sorted_by_composite_class = sorted(self.objects.values(), key=key)
            for composite_name, objs in itertools.groupby(objs_sorted_by_composite_class, key):
                if composite_name:
                    if composite_name not in self.classes_by_name.keys():
                        raise Exception("Unknown composite class " + composite_name)
                    objs_to_combine = dict([(obj.section, obj) for obj in objs])
                    self.objects[composite_name] = self.classes_by_name[composite_name](**objs_to_combine)
                    objs_merged.extend(objs_to_combine.keys())

            for name in objs_merged:
                del self.objects[name]

        def get_all_objects(self):
            return self.objects

        def get_elements(self, name):
            return self.objects[name].get_elements()

    element_classes = ElementClasses()

    @element_classes.append
    class Notes(INPElementClass):
        inp_label = '[TITLE]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('NotesText', str)])
            self.name_field = None
            self.desc_field = None
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            notes = {'NotesText' : ''}
            blanks = ''
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if i == self.start_lineno:
                    continue
                if re.match('[\s]*\n', line):
                    blanks += line
                else:
                    if blanks:
                        line = blanks + line
                        blanks = ''
                    notes[self.fields.keys()[0]] += line

            notes['NotesText'] = notes['NotesText'].strip()
            self.elements = [notes] if notes['NotesText'] else []

        def inp_lines(self, **kwargs):
            notes = self.elements[0]['NotesText'].decode('string-escape').split('\n')
            inp_lines = [self.inp_label]
            inp_lines.extend(notes)
            return inp_lines

    @element_classes.append
    class Options(INPElementClass):
        inp_label = '[OPTIONS]'
        def __init__(self, start_lineno=None, end_lineno=None, elements=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.infil_key = 'INFILTRATION'
            self.fields = OrderedDict([('FLOW_UNITS', str),
                                       (self.infil_key, str),
                                       ('FLOW_ROUTING', str),
                                       ('START_DATE', str),
                                       ('START_TIME', str),
                                       ('REPORT_START_DATE', str),
                                       ('REPORT_START_TIME', str),
                                       ('END_DATE', str),
                                       ('END_TIME', str),
                                       ('SWEEP_START', str),
                                       ('SWEEP_END', str),
                                       ('DRY_DAYS', float),
                                       ('REPORT_STEP', str),
                                       ('WET_STEP', str),
                                       ('DRY_STEP', str),
                                       ('ROUTING_STEP', str),
                                       ('ALLOW_PONDING', str),
                                       ('INERTIAL_DAMPING', str),
                                       ('VARIABLE_STEP', float),
                                       ('LENGTHENING_STEP', float),
                                       ('MIN_SURFAREA', float),
                                       ('NORMAL_FLOW_LIMITED', str),
                                       ('SKIP_STEADY_STATE', str),
                                       ('FORCE_MAIN_EQUATION', str),
                                       ('LINK_OFFSETS', str),
                                       ('MIN_SLOPE', float),
                                       ('IGNORE_RAINFALL', str),
                                       ('IGNORE_GROUNDWATER', str)])
            self.name_field = None
            self.desc_field = None
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            options = {} 
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if re.match(self.pats['desc'], line) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    line = line.split()
                    if len(line) != 2:
                        if line[2].startswith(';'):
                            raise Exception("Comments in [OPTIONS] are not supported. Please remove them and try again.")
                        else:
                            raise self._unexpected_line_exc(line)
                    param = line[0].upper()
                    value = line[1]
                    options[param] = self.fields[param](value)

            if all([value is None for value in options.values()]):
                self.elements = []
            else:
                for field in self.fields.keys():
                    if field not in options.keys():
                        options[field] = None
                
                self.elements = [options]

        def inp_lines(self, **kwargs):
            inp_lines = [self.inp_label]
            opts = self.elements[0]

            label_col_width = max([len(name) for name in self.fields.keys()])
            format_str = '{:<' + str(label_col_width) + '}'
            for name in self.fields.keys():
                value = opts[name] 
                if value is None:
                    continue
                elif isinstance(value, float):
                    if value == int(value):
                        value = int(value)
                inp_lines.append(format_str.format(name) + ' ' * 10 + str(value))

            return inp_lines

    @element_classes.append
    class Files(INPElementClass):
        inp_label = '[FILES]' 
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Usage', str),
                                       ('FileType', str),
                                       ('FileName', str)])
            self.name_field = 'Name'
            self.desc_field = None
            self.ordinal_field = 'Ordinal'
            self.md5_field = 'FileMD5'
            self.composite_name = ['Usage', 'FileType', self.ordinal_field]
            self.sort_by = [self.ordinal_field]
            self.files = {}
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            if self.inp_path:
                current_file_num = 1
                for i in range(self.start_lineno, self.end_lineno):
                    line = self.getline(i)
                    if re.match(self.pats['desc'], line) or re.match(self.pats['blank_or_tag'], line):
                        continue
                    else:
                        line = line.split(None, 2)
                        if len(line) != len(self.fields):
                            raise self._unexpected_line_exc(line)
                        for j, value in enumerate(line):
                            if value is not None:
                                line[j] = self.fields.values()[j](value)
                        params = dict(zip(self.fields.keys(), line))
                        params[self.ordinal_field] = current_file_num
                        name = ':'.join([params['Usage'], params['FileType'], str(current_file_num)])
                        params[self.name_field] = ':'.join([str(params[field]) for field in self.composite_name])
                        if params['Usage'] == 'USE' and self.require_support_files:
                            filepath = params['FileName'].strip(' \n\t"\'')
                            if not os.path.exists(filepath):
                                filepath = os.path.join(os.path.dirname(self.inp_path), filepath)

                            if not os.path.exists(filepath):
                                raise Exception("Can't find support file '" + params['FileName'] + "' referenced in [FILES]")
                            else:
                                params['FileName'] = '"' + os.path.basename(filepath) + '"'
                                with open(filepath, 'rb') as f:
                                    fcontents = f.read()
                                md5 = hashlib.md5(fcontents).hexdigest()
                                params['FileMD5'] = md5
                                self.files[filepath] = md5
                        else:
                            if self.require_support_files:
                                params['FileName'] = '"' + os.path.basename(params['FileName'].strip(' \n\t"\'')) + '"'
                            else:
                                params['FileName'] = params['FileName'].strip()
                            params['FileMD5'] = None
                        self.elements.append(params)
                        current_file_num += 1
            else:
                raise Exception("Can't parse inp file, no path supplied.")

    @element_classes.append
    class Evaporation(INPElementClass):
        inp_label = '[EVAPORATION]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Type', str), ('Parameters', str), ('Recovery', str), ('DryOnly', str)])
            self.name_field = None
            self.desc_field = None
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            evaporation = {'Recovery' : None}
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if re.match(self.pats['desc'], line) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    line = line.split()
                    marker = line[0]

                    if marker in ('CONSTANT', 'TIMESERIES', 'FILE', 'TEMPERATURE', 'MONTHLY'):
                        evaporation['Type'] = marker
                        parameters = ' '.join(line[1:])

                        if len(parameters) == 0:
                            parameters = None

                        evaporation['Parameters'] = parameters
                    elif marker in ('RECOVERY', 'DRY_ONLY'):
                        if len(line) != 2:
                            raise self._unexpected_line_exc(line)
                        else:
                            if marker == 'RECOVERY':
                                field = 'Recovery'
                            elif marker == 'DRY_ONLY':
                                field = 'DryOnly'

                            evaporation[field] = line[1]
                    else:
                        raise self._unexpected_line_exc(line)

            if all([value is None for value in evaporation.values()]):
                self.elements = []
            else:
                self.elements = [evaporation]

        def inp_lines(self, **kwargs):
            if not self.elements:
                return []

            evap = self.elements[0]

            inp_lines = [self.inp_label,
                 ';;Type       Parameters',
                 ';;---------- ----------']

            spacer = ' ' * 5
            recovery = evap['Recovery']
            dryonly = evap['DryOnly']

            inp_lines.append(spacer.join([evap['Type'], evap['Parameters']]))
            if evap['Recovery']:
                inp_lines.append(spacer.join(['RECOVERY', evap['Recovery']]))

            if evap['DryOnly']:
                inp_lines.append(spacer.join(['DRY_ONLY', evap['DryOnly']]))

            return inp_lines
    
    @element_classes.append
    class Junctions(INPElementClass):
        inp_label = '[JUNCTIONS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str), 
                                       ('InvertElevation', float),
                                       ('MaxDepth', float),
                                       ('InitDepth', float),
                                       ('SurchargeDepth', float),
                                       ('PondedArea', float)])
            self.subclasses = {'Coordinates' : False, 'Tags' : False, 'RDII' : False}
            self.tag_type = 'Node'
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)

            return line, unmarked_desc, None

    @element_classes.append
    class Outfalls(INPElementClass):
        inp_label = '[OUTFALLS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('InvertElevation', float),
                                       ('OutfallType', str),
                                       ('TimeSeriesName', str),
                                       ('TideGate', str)])
            self.subclasses = {'Coordinates' : False, 'Tags' : False, 'RDII' : False}
            self.tag_type = 'Node'
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            if len(line) == (len(self.fields) - 1):
                line.insert(3, None)
            elif len(line) == len(self.fields) and self.long_line_comment:
                if re.match('yes|no', line[len(self.fields)-2], re.IGNORECASE):
                    line.insert(3, None)
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
            elif len(line) > len(self.fields):
                if self.long_line_comment:
                    if re.match('yes|no', line[len(self.fields)-2], re.IGNORECASE):
                        line.insert(3, None)
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)

            return line, unmarked_desc, None

    @element_classes.append
    class Dividers(INPElementClass):
        inp_label = '[DIVIDERS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('InvertElevation', float),
                                       ('DivertedLink', str),
                                       ('DividerType', str),
                                       ('CutoffFlow', float),
                                       ('CurveName', str),
                                       ('MinFlow', float),
                                       ('WeirMaxDepth', float),
                                       ('Coefficient', float),
                                       ('MaxDepth', float),
                                       ('InitDepth', float),
                                       ('SurchargeDepth', float),
                                       ('PondedArea', float)])
            self.subclasses = {'Coordinates' : False, 'Tags' : False, 'RDII' : False}
            self.tag_type = 'Node'

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            if line[3] == 'OVERFLOW' and (len(line) == len(self.fields) - 5 or self.long_line_comment):
                line = line[0:4] + [None]*5 + line[4:]
            elif line[3] == 'WEIR' and (len(line) == len(self.fields) - 2 or self.long_line_comment):
                line = line[0:4] + [None]*2 + line[4:]
            elif ( line[3] == 'CUTOFF' or line[3] == 'TABULAR' ) and (len(line) == len(self.fields) - 4 \
                    or self.long_line_comment):
                if line[3] == 'CUTOFF':
                    line = line[0:4] + line[4:5] + [None]*4 + line[5:]
                else:
                    line = line[0:4] + [None] + line[4:5] + [None]*3 + line[5:]
            else:
                raise self._unexpected_line_exc(line)

            if len(line) > len(self.fields):
                if self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)

            return line, unmarked_desc, None
        
    @element_classes.append
    class Storage(INPElementClass):
        inp_label = '[STORAGE]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('InvertElevation', float),
                                       ('MaxDepth', float),
                                       ('InitDepth', float),
                                       ('StorageCurve', str),
                                       ('CurveName', str),
                                       ('CurveCoeff', float),
                                       ('CurveExponent', float),
                                       ('CurveConstant', float),
                                       ('PondedArea', float),
                                       ('EvapFactor', float),
                                       ('SuctionHead', float),
                                       ('Conductivity', float),
                                       ('InitialDeficit', float)])
            self.subclasses = {'Coordinates' : False, 'Tags' : False, 'RDII' : False}
            self.tag_type = 'Node'

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            fields = self.fields.keys()
            storage_curve_index = fields.index('StorageCurve')
            curve_marker = line[storage_curve_index] # should be 'FUNCTIONAL' or 'TABULAR'
            if curve_marker == 'TABULAR':
                none_fields = ['CurveCoeff', 'CurveExponent', 'CurveConstant']
                for i in [fields.index(field) for field in none_fields]:
                    line.insert(i, None)
            elif curve_marker == 'FUNCTIONAL':
                none_field = 'CurveName'
                idx = fields.index(none_field)
                line.insert(idx, None)
            else:
                raise self._unexpected_line_exc(line)

            if len(line) != len(self.fields):
                if len(line) == len(self.fields) - 3:
                    line.extend([None for i in xrange(3)])
                elif self.long_line_comment:
                    if len(line) < len(self.fields):
                        unmarked_desc = ' '.join(line[len(self.fields)-3:]).strip()
                        line = line[:len(self.fields)-3]
                        line.extend([None for i in xrange(3)])
                    else:
                        last_three_params = line[len(self.fields)-3:len(self.fields)]
                        try:
                            _ = [float(x) for x in last_three_params]
                        except:
                            unmarked_desc = ' '.join(line[len(self.fields)-3:]).strip()
                            line = line[:len(self.fields)-3]
                        else:
                            unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                            line = line[:len(self.fields)]
            else:
                if self.long_line_comment:
                    last_three_params = line[len(self.fields)-3:]
                    try:
                        _ = [float(x) for x in last_three_params]
                    except:
                        unmarked_desc = ' '.join(line[len(self.fields)-3:]).strip()
                        line = line[:len(self.fields)-3]

            return line, unmarked_desc, None

    @element_classes.append
    class Coordinates(INPElementClass):
        inp_label = '[COORDINATES]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('XCoordinate', float),
                                       ('YCoordinate', float)])
            self.desc_field = 'CoordinateDescription'
            self.defaults = {'XCoordinate' : None, 'YCoordinate' : None}
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)

            return line, unmarked_desc, None

    @element_classes.append
    class Conduits(INPElementClass):
        inp_label = '[CONDUITS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.inp_label = self.__class__.inp_label
            self.section = self.__class__.__name__
            self.fields = OrderedDict([('Name', str),
                                       ('InletNode', str),
                                       ('OutletNode', str),
                                       ('Length', float),
                                       ('ManningN', float),
                                       ('InletOffset', float),
                                       ('OutletOffset', float),
                                       ('InitFlow', float),
                                       ('MaxFlow', float)])
            self.subclasses = {'XSections' : True, 'Losses' : False, 'Tags' : False}
            self.tag_type = 'Link'
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)

            return line, unmarked_desc, None

    @element_classes.append
    class Pumps(INPElementClass):
        inp_label = '[PUMPS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('InletNode', str),
                                       ('OutletNode', str),
                                       ('PumpCurve', str),
                                       ('InitStatus', str),
                                       ('StartupDepth', float),
                                       ('ShutoffDepth', float)])
            self.subclasses = {'Tags' : False}
            self.tag_type = 'Link'
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)
            return line, unmarked_desc, None
        

    @element_classes.append
    class Orifices(INPElementClass):
        inp_label = '[ORIFICES]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('InletNode', str),
                                       ('OutletNode', str),
                                       ('Type', str),
                                       ('InletOffset', float),
                                       ('DischargeCoeff', float),
                                       ('FlapGate', str),
                                       ('MoveTime', float)])
            self.subclasses = {'XSections' : True, 'Tags' : False}
            self.tag_type = 'Link'
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()
            
        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            if len(line) != len(self.fields):
                if len(line) > len(self.fields):
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)
            return line, unmarked_desc, None

    @element_classes.append
    class Weirs(INPElementClass):
        inp_label = '[WEIRS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('InletNode', str),
                                       ('OutletNode', str),
                                       ('Type', str),
                                       ('InletOffset', float),
                                       ('DischargeCoeff', float),
                                       ('FlapGate', str),
                                       ('EndContractions', int),
                                       ('EndCoeff', float)])
            self.subclasses = {'XSections' : True, 'Tags' : False}
            self.tag_type = 'Link'
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            if len(line) != len(self.fields):
                if len(line) == (len(self.fields) - 1):
                    line.append(None)
                elif len(line) > len(self.fields) and self.long_line_comment:
                    try:
                        _ = float(line[len(self.fields)-1])
                    except:
                        unmarked_desc = ' '.join(line[len(self.fields) - 1:]).strip()
                        line = line[:len(self.fields)-1]
                        line.append(None)
                    else:
                        unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                        line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)
            else:
                last_param = line[len(self.fields)-1]
                try:
                    _ = float(last_param)
                except:
                    if self.long_line_comment:
                        unmarked_desc = ' '.join(line[len(self.fields)-1:]).strip()
                        line = line[:len(self.fields)-1]
                        line.append(None)
                    else:
                        raise self._unexpected_line_exc(line)
        
            return line, unmarked_desc, None

    @element_classes.append
    class Outlets(INPElementClass):
        inp_label = '[OUTLETS]' 
        def __init__(self, start_lineno=None, end_lineno=None, elements=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('InletNode', str),
                                       ('OutletNode', str),
                                       ('OutflowHeight', float),
                                       ('OutletType', str),
                                       ('FunctionalCoeff', float),
                                       ('FunctionalExponent', float),
                                       ('CurveName', str),
                                       ('FlapGate', str)])
            self.subclasses = {'Tags' : False}
            self.tag_type = 'Link'

            if start_lineno is not None and end_lineno is not None:
                self.parse()
        
        def _parse_line(self, line):
            line = line.split()
            unmarked_desc = ''
            fields = self.fields.keys()
            if re.match('^FUNCTIONAL', line[fields.index('OutletType')]):
                line.insert(fields.index('CurveName'), None)
            elif re.match('^TABULAR', line[fields.index('OutletType')]):
                line.insert(fields.index('FunctionalCoeff'), None)
                line.insert(fields.index('FunctionalExponent'), None)
            else:
                raise self._unexpected_line_exc(line)
                
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)

            return line, unmarked_desc, None

    @element_classes.append
    class XSections(INPElementClass):
        inp_label = '[XSECTIONS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('PipeShape', str),
                                       ('Geom1', str),
                                       ('Geom2', str),
                                       ('Geom3', float),
                                       ('Geom4', float),
                                       ('Barrels', float),
                                       ('CulvertCode', str)])
            self.desc_field = 'XSectionsDescription'
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            line = line.split()
            unmarked_desc = ''
            if len(line) == len(self.fields):
                try:
                    _ = [float(x) for x in line[:-3:-1]]
                except:
                    if self.long_line_comment:
                        unmarked_desc = ' '.join(line[-2:1]).strip()
                        line = line[:-2]
                        line.extend([None, None])
                    else:
                        raise self._unexpected_line_exc(line)
            elif len(line) == len(self.fields) - 1:
                if self.long_line_comment:
                    last_param = line[-1]
                    try:
                        assert int(last_param) == float(last_param)
                    except:
                        unmarked_desc = line[-1]
                        line = line[:-1]
                line.extend([None, None])
            elif len(line) == len(self.fields) - 2:
                line.extend([None, None])
            elif len(line) > len(self.fields):
                if self.long_line_comment:
                    penult_param = line[len(self.fields)-2]
                    try:
                        assert float(penult_param) == int(penult_param)
                    except:
                        unmarked_desc = ' '.join(line[len(self.fields)-2:]).strip()
                        line = line[:len(self.fields)-2]
                        line.extend([None, None])
                    else:
                        raise self._ambiguous_line_exc(line)

            return line, unmarked_desc, None

    @element_classes.append
    class Losses(INPElementClass):
        inp_label = '[LOSSES]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('EntryLoss', float),
                                       ('ExitLoss', float),
                                       ('AvgLoss', float),
                                       ('FlapGate', str)])
            self.desc_field = 'LossesDescription'
            default_fields = self.fields.keys()
            default_fields.remove(self.name_field)
            self.defaults = dict([(field, None) for field in default_fields])

            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            line = line.split()
            unmarked_desc = ''
            if len(line) != len(self.fields):
                if len(line) > len(self.fields):
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)
            return line, unmarked_desc, None

    @element_classes.append
    class RainGages(INPElementClass):
        inp_label = '[RAINGAGES]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str), 
                                       ('RainType', str), 
                                       ('Interval', str), 
                                       ('SnowCatch', float), 
                                       ('Source', str), 
                                       ('SourceName', str), 
                                       ('StationID', str), 
                                       ('Units', str)])
            self.subclasses = {'Symbols' : False, 'Tags' : False}
            self.tag_type = 'Gage'
            self.md5_field = 'FileMD5'
            self.files = {}

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            original_line = line
            line = line.split()
            if line[self.fields.keys().index('Source')] == 'TIMESERIES':
                # implies no gage number or units
                num_fields_TIMESERIES = len(self.fields) - 2
                if len(line) == num_fields_TIMESERIES:
                    line.extend([None, None])
                elif len(line) > num_fields_TIMESERIES and self.long_line_comment:
                    unmarked_desc = ' '.join(line[num_fields_TIMESERIES:]).strip()
                    line = line[:num_fields_TIMESERIES]
                    line.extend([None, None])
                else:
                    raise self._unexpected_line_exc(line)
            else:
                num_remaining_params_after_path = 2

                start_of_fileref = 5
                val = line[start_of_fileref]
                has_quote = re.match('\'|"', val)
                end_of_fileref = None
                if has_quote:
                    quote_char = has_quote.group()
                    for i, val in enumerate(line[start_of_fileref:]):
                        has_end_quote = re.search('\'|"$', val)
                        if has_end_quote:
                            end_of_fileref = start_of_fileref + i
                            break
                    
                    if not end_of_fileref:
                        raise Exception('The file reference on the following line is missing a quote: ' + str(line))
                    num_params_after_fileref = 2
                    del line[start_of_fileref:end_of_fileref + 1]
                    unsplit_fileref = '"' + original_line.split(quote_char)[1].strip() + '"'
                    line.insert(start_of_fileref, unsplit_fileref)
                else:
                    line[start_of_fileref] = '"' + line[start_of_fileref] + '"'

                if len(line) < len(self.fields):
                    raise self._unexpected_line_exc(original_line)
                elif len(line) > len(self.fields):
                    if self.long_line_comment:
                        unmarked_desc = ' '.join(line[len(self.fields):])
                        line = line[:len(self.fields)]
                    else:
                        raise self._unexpected_line_exc(line)

            md5 = None
            source_idx = self.fields.keys().index('Source')
            sourcename_idx = self.fields.keys().index('SourceName')
            if line[source_idx] == 'FILE' and self.require_support_files:
                filepath = line[sourcename_idx].strip(' \t\n"\'')
                if not os.path.exists(filepath):
                    filepath = os.path.join(os.path.dirname(self.inp_path), line[sourcename_idx].strip(' \t\n"'))

                if not os.path.exists(filepath):
                    raise self._missing_file_exc(line[sourcename_idx])
                elif os.path.exists(filepath):
                    line[sourcename_idx] = '"' + os.path.basename(filepath) + '"'
                    with open(filepath, 'rb') as f:
                        fcontents = f.read()
                    md5 = hashlib.md5(fcontents).hexdigest()
                    self.files[filepath] = md5

            return line, unmarked_desc, md5

    @element_classes.append
    class Symbols(INPElementClass):
        inp_label = '[SYMBOLS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
                
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str), 
                                       ('XCoordinate', float), 
                                       ('YCoordinate', float)])
            self.desc_field = 'CoordinateDescription'
            self.defaults = {'XCoordinate' : None, 'YCoordinate' : None}

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            line = line.split()
            unmarked_desc = ''
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else: 
                    raise self._unexpected_line_exc(line)

            return line, unmarked_desc, None
    
    @element_classes.append
    class Pollutants(INPElementClass):
        inp_label = '[POLLUTANTS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('MassUnits', str),
                                       ('RainConcen', float),
                                       ('GWConcen', float),
                                       ('IIConcen', float),
                                       ('DecayCoeff', float),
                                       ('SnowOnly', str),
                                       ('CoPollutant', str),
                                       ('CoPollutantFraction', float),
                                       ('DWFConcen', float)])

            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            line = line.split()
            unmarked_desc = ''
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)

            return line, unmarked_desc, None

    @element_classes.append
    class LandUses(INPElementClass):
        inp_label = '[LANDUSES]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('CleaningInterval', float),
                                       ('Availability', float),
                                       ('LastCleaned', float)])
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            line = line.split()
            unmarked_desc = ''
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)

            return line, unmarked_desc, None

    @element_classes.append
    class BuildUp(INPElementClass):
        inp_label = '[BUILDUP]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label 
            self.fields = OrderedDict([('LandUse', str),
                                       ('Pollutant', str),
                                       ('Formula', str),
                                       ('Coeff1', float),
                                       ('Coeff2', float),
                                       ('Coeff3', float),
                                       ('TimeSeries', str),
                                       ('Normalizer', str)])
            self.composite_name = ['LandUse', 'Pollutant']
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            line = line.split()
            unmarked_desc = ''
            fields = self.fields.keys()
            timeseries_marker = line[fields.index('Coeff3')]
            try:
                dummy = float(timeseries_marker)
            except:
                line.insert(fields.index('Coeff3'), None)
            else:
                line.insert(fields.index('TimeSeries'), None)

            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)
            return line, unmarked_desc, None
    
    @element_classes.append
    class WashOff(INPElementClass):
        inp_label = '[WASHOFF]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('LandUse', str),
                                       ('Pollutant', str),
                                       ('Formula', str),
                                       ('Coeff1', float),
                                       ('Coeff2', float),
                                       ('CleaningEfficiency', float),
                                       ('BMPEfficiency', float)])
            self.composite_name = ['LandUse', 'Pollutant']
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            line = line.split()
            unmarked_desc = ''
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)
            return line, unmarked_desc, None
    
    @element_classes.append
    class Inflows(INPElementClass):
        inp_label = '[INFLOWS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Node', str),
                                       ('Parameter', str),
                                       ('TimeSeries', str),
                                       ('ParameterType', str),
                                       ('UnitsFactor', float),
                                       ('ScaleFactor', float),
                                       ('BaselineValue', float),
                                       ('BaselinePattern', str)])
            self.composite_name = ['Node', 'Parameter']
            self.defaults = {}
            for fieldname in self.fields.keys():
                if fieldname not in self.composite_name:
                    self.defaults[fieldname] = None
            self.composite_class = 'NodeInflows'
            self.desc_field = 'InflowsDescription'

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            line = line.split()
            if len(line) != len(self.fields):
                if len(line) == (len(self.fields) - 1):
                    # baseline pattern is empty
                    line.append(None)
                elif len(line) == (len(self.fields) - 2):
                    # baseline value and baseline pattern are empty
                    line.extend([None, None])
                elif len(line) > len(self.fields) and self.long_line_comment:
                    raise self._ambiguous_line_exc(line)
                else:
                    raise self._unexpected_line_exc(line)

            return line, None, None

    @element_classes.append
    class DWF(INPElementClass):
        inp_label = '[DWF]' 
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Node', str),
                                       ('Parameter', str),
                                       ('AvgValue', float),
                                       ('DWFTimePattern1', str),
                                       ('DWFTimePattern2', str),
                                       ('DWFTimePattern3', str),
                                       ('DWFTimePattern4', str)])
            self.composite_name = ['Node', 'Parameter']
            self.defaults = {}
            for fieldname in self.fields.keys():
                if fieldname not in self.composite_name:
                    self.defaults[fieldname] = None
            self.composite_class = 'NodeInflows'
            self.desc_field = 'DWFDescription'

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            line = line.split()
            if len(line) != len(self.fields):
                if len(line) < len(self.fields):
                    if len(line) >= len(self.fields) - 4:
                        line.extend([None for j in range(len(self.fields) - len(line))])
                    else:
                        raise self._unexpected_line_exc(line)
                elif len(line) > len(self.fields):
                    if self.long_line_comment:
                        raise self._ambiguous_line_exc(line)
                    else:
                        raise self._unexpected_line_exc(line)
            return line, None, None

    @element_classes.append
    class RDII(INPElementClass):
        inp_label = '[RDII]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('UnitHydrograph', str),
                                       ('SewerArea', float)])
            self.desc_field = 'RDIIDescription'
            self.defaults = {'UnitHydrograph' : None, 'SewerArea' : None}

            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)

            return line, unmarked_desc, None
    
    @element_classes.append
    class Aquifers(INPElementClass):
        inp_label = '[AQUIFERS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('Porosity', float),
                                       ('WiltPoint', float),
                                       ('FieldCapacity', float),
                                       ('HydCon', float),
                                       ('CondSlope', float),
                                       ('TensionSlope', float),
                                       ('UpperEvap', float),
                                       ('LowerEvap', float),
                                       ('LowerLoss', float),
                                       ('BottomElev', float),
                                       ('WaterTable', float),
                                       ('UpperMoist', float)])
            
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)

            return line, unmarked_desc, None
    
    @element_classes.append
    class Subcatchments(INPElementClass):
        inp_label = '[SUBCATCHMENTS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str), 
                                       ('Raingage', str),
                                       ('Outlet', str),
                                       ('Area', float),
                                       ('PctImperv', float),
                                       ('Width', float),
                                       ('PctSlope', float),
                                       ('CurbLength', float),
                                       ('SnowPack', str)])
            self.subclasses = {'Subareas' : True, 'Groundwater' : False, 'Infiltration' : True, 'Tags' : False}
            self.tag_type = 'Subcatch'

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            line = line.split()
            num_fields_NoSnowPack = len(self.fields) - 1
            if len(line) != len(self.fields):
                if len(line) == num_fields_NoSnowPack:
                    line.append(None)
                elif len(line) > len(self.fields) and self.long_line_comment:
                    raise self._ambiguous_line_exc(line)
                else:
                    raise self._unexpected_line_exc(line)
            
            return line, None, None
    
    @element_classes.append
    class Subareas(INPElementClass):
        inp_label = '[SUBAREAS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('NImperv', float),
                                       ('NPerv', float),
                                       ('SImperv', float),
                                       ('SPerv', float),
                                       ('PctZero', float),
                                       ('RouteTo', str),
                                       ('PctRouted', float)])
            self.desc_field = 'SubareasDescription'

            if start_lineno and end_lineno:
                self.parse()

        def _parse_line(self, line):
            num_fields_NoPctRouted = len(self.fields) - 1
            line = line.split()
            unmarked_desc = ''
            if len(line) != len(self.fields):
                if len(line) == num_fields_NoPctRouted:
                    line.append(None)
                elif len(line) > len(self.fields) and self.long_line_comment:
                    last_param = line[len(self.fields)-1]
                    try:
                        last_param = float(last_param)
                        assert last_param <= 100 and last_param >= 0
                    except:
                        unmarked_desc = ' '.join(line[num_fields_NoPctRouted:]).strip()
                        line = line[:num_fields_NoPctRouted]
                        line.append(None)
                    else:
                        unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                        line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)
            elif self.long_line_comment:
                try:
                    last_param = float(line[-1])
                    assert last_param <= 100 and last_param >= 0
                except:
                    unmarked_desc = line[-1]
                    line = line[:-1]
                    line.append(None)

            return line, unmarked_desc, None


    @element_classes.append
    class Infiltration(INPElementClass):
        inp_label = '[INFILTRATION]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.greenampt_fields = OrderedDict([('SuctionHead', float),
                                                 ('HydCon', float),
                                                 ('IMDmax', float)])
            self.horton_fields = OrderedDict([('MaxRate', float),
                                              ('MinRate', float),
                                              ('Decay', float),
                                              ('DryTime', float),
                                              ('MaxInfil', float)])

            self.fields = OrderedDict([('Name', str)] + self.greenampt_fields.items() + self.horton_fields.items())
            self.desc_field = 'InfiltrationDescription'
            self.defaults = dict([(field, None) for field in self.fields])

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            if len(line) < len(self.horton_fields):
                primary_fields = self.greenampt_fields
                secondary_fields = self.horton_fields
            else:
                primary_fields = self.horton_fields
                secondary_fields = self.greenampt_fields
                for i in range(1, 6):
                    try:
                        _ = float(line[i])
                    except:
                        primary_fields = self.greenampt_fields
                        secondary_fields = self.horton_fields

            primary_length = len(primary_fields) + 1 # fields plus name field
            if len(line) != primary_length:
                if len(line) > primary_length and self.long_line_comment:
                    unmarked_desc = ' '.join(line[primary_length:]).strip()
                    line = line[:primary_length]
                else:
                    raise self._unexpected_line_exc(line)

            defaults = [None for field in secondary_fields.keys()]
            if primary_fields == self.greenampt_fields:
                line = line + defaults
            else:
                line = line[:1] + defaults + line[1:]

            return line, unmarked_desc, None

    @element_classes.append
    class Groundwater(INPElementClass):
        inp_label = '[GROUNDWATER]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('Aquifer', str),
                                       ('GWReceivingNode', str),
                                       ('GWSurfaceElev', float),
                                       ('GWFlowCoeff', float),
                                       ('GWFlowExpon', float),
                                       ('SWFlowCoeff', float),
                                       ('SWFlowExpon', float),
                                       ('SWGWInteractionCoeff', float),
                                       ('SWFixedDepth', float),
                                       ('GWThresholdElevation', float)])
            self.desc_field = 'GWDescription'
            default_fields = self.fields.keys()
            default_fields.remove(self.name_field)
            self.defaults = dict([(field, None) for field in default_fields])

            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            num_fields_NoElev = len(self.fields) - 1
            line = line.split()
            unmarked_desc = ''
            if len(line) != len(self.fields):
                if len(line) == (num_fields_NoElev):
                    line.append(None)
                elif len(line) > len(self.fields) and self.long_line_comment:
                    last_param = line[len(self.fields)-1]
                    try:
                        _ = float(last_param)
                    except:
                        unmarked_desc = ' '.join(line[num_fields_NoElev:]).strip()
                        line = line[:num_fields_NoElev]
                        line.append(None)
                    else:
                        unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                        line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)
            elif self.long_line_comment:
                try:
                    last_param = float(line[-1])
                except:
                    unmarked_desc = line[-1]
                    line = line[:-1]
                    line.append(None)

            return line, unmarked_desc, None

    @element_classes.append
    class Coverages(INPElementClass):
        inp_label = '[COVERAGES]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Subcatchment', str),
                                       ('LandUse', str),
                                       ('PercentArea', float)])
            self.composite_name = ['Subcatchment', 'LandUse']

            if start_lineno is not None and end_lineno is not None:
                self.parse()
            
        def _parse_line(self, line):
            line = line.split()
            unmarked_desc = ''
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)
            return line, unmarked_desc, None

    @element_classes.append
    class Loadings(INPElementClass):
        inp_label = '[LOADINGS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Subcatchment', str),
                                       ('Pollutant', str),
                                       ('Loading', float)])
            self.composite_name = ['Subcatchment', 'Pollutant']
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            unmarked_desc = ''
            line = line.split()
            if len(line) != len(self.fields):
                if len(line) > len(self.fields) and self.long_line_comment:
                    unmarked_desc = ' '.join(line[len(self.fields):]).strip()
                    line = line[:len(self.fields)]
                else:
                    raise self._unexpected_line_exc(line)

            return line, unmarked_desc, None

    @element_classes.append
    class Treatments(INPElementClass):
        inp_label = '[TREATMENT]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Node', str),
                                       ('Pollutant', str),
                                       ('Formula', str)])
            self.composite_name = ['Node', 'Pollutant']

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def _parse_line(self, line):
            line = line.split(None, 2)
            if len(line) != len(self.fields):
                raise self._unexpected_line_exc(line)
            line[2] = line[2].strip()

            return line, None, None

    @element_classes.append
    class Vertices(INPElementClass):
        inp_label = '[VERTICES]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Link', str),
                                       ('XCoordinate', float),
                                       ('YCoordinate', float)])
            
            self.ordinal_field = 'Ordinal'
            self.composite_name = ['Link', 'Ordinal']
            self.inp_grouping = 'Link'
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            prev_link = ""
            past_header = False
            element_desc = ''
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if (re.match(self.pats['header'], line) and not past_header) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    past_header = True
                    if re.match(self.pats['desc'], line):
                        line = line.strip(self.pats['desc_whitespace'])
                        element_desc = line if not element_desc else element_desc + '\n' + line
                        continue
                    else:
                        line_descs = {'marked' : '', 'unmarked' : ''}

                        if re.search(self.pats['semicolon'], line):
                            line, line_descs['marked'] = re.split(self.pats['adj_semicolons'], line, maxsplit=1)
                            line_descs['marked'] = line_descs['marked'].strip(self.pats['desc_whitespace'])

                        line = line.split()
                        if len(line) != len(self.fields):
                            if len(line) > len(self.fields) and self.long_line_comment:
                                line_descs['unmarked'] = ' '.join(line[len(self.fields):]).strip()
                                line = line[:len(self.fields)]
                            else:
                                raise self._unexpected_line_exc(line)

                        if all(line_descs.values()):
                            line_desc = ' ; '.join([line_descs['unmarked'], line_descs['marked']])
                        elif line_descs['marked']:
                            line_desc = line_descs['marked']
                        elif line_descs['unmarked']:
                            line_desc = line_descs['unmarked']
                        else:
                            line_desc = ''

                        if line_desc:
                            element_desc = line_desc if not element_desc else '\n'.join([element_desc, line_desc])

                        line = [self.fields.values()[j](value) if value else value for j, value in enumerate(line)]
                        params = dict(zip(self.fields.keys(), line))
                        current_link = params['Link']
                        if current_link != prev_link:
                            coord_ordinal = 1
                        else:
                            coord_ordinal = coord_ordinal + 1
                        params[self.ordinal_field] = coord_ordinal
                        params[self.name_field] = ':'.join([str(params[field]) for field in self.composite_name])
                        element_desc = element_desc.replace('\\n', '\n') 
                        params[self.desc_field] = element_desc
                        element_desc = ''
                        prev_link = current_link
                        self.elements.append(params)

    @element_classes.append
    class PolygonPoints(INPElementClass):
        inp_label = '[POLYGONS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Subcatchment', str),
                                       ('XCoordinate', float),
                                       ('YCoordinate', float)])

            self.ordinal_field = 'Ordinal'
            self.composite_name = ['Subcatchment', self.ordinal_field]
            self.inp_grouping = 'Subcatchment'
            self.sort_by = ['Subcatchment']
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            prev_catch = ""
            past_header = False
            element_desc = ''
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if (re.match(self.pats['header'], line) and not past_header) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    past_header = True
                    if re.match(self.pats['desc'], line):
                        desc = line.strip(self.pats['desc_whitespace'])
                        element_desc = desc if not element_desc else '\n'.join([element_desc, desc])
                        continue
                    else:
                        line_descs = {'marked' : '', 'unmarked' : ''}
                        if re.search(self.pats['semicolon'], line):
                            line, line_descs['marked'] = re.split(self.pats['adj_semicolons'], line, maxsplit=1)
                            line_descs['marked'] = line_descs['marked'].strip(self.pats['desc_whitespace'])

                        line = line.split()

                        if len(line) != len(self.fields):
                            if len(line) > len(self.fields) and self.long_line_comment:
                                line_descs['unmarked'] = ' '.join(line[len(self.fields):]).strip()
                                line = line[:len(self.fields)]
                            else:
                                raise self._unexpected_line_exc(self.section, line)

                        if all(line_descs.values()):
                            line_desc = ' ; '.join([line_descs['unmarked'], line_descs['marked']])
                        elif line_descs['marked']:
                            line_desc = line_descs['marked']
                        elif line_descs['unmarked']:
                            line_desc = line_descs['unmarked']
                        else:
                            line_desc = ''

                        if line_desc:
                            element_desc = line_desc if not element_desc else '\n'.join([element_desc, line_desc])

                        line = [self.fields.values()[j](value) if value else value for j, value in enumerate(line)]
                        params = dict(zip(self.fields.keys(), line))
                        element_desc = element_desc.replace('\\n', '\n')
                        params[self.desc_field] = element_desc
                        current_catch = params['Subcatchment']
                        if current_catch != prev_catch:
                            coord_ordinal = 1
                        else:
                            coord_ordinal = coord_ordinal + 1
                        params[self.ordinal_field] = coord_ordinal
                        name = ':'.join([str(params[field]) for field in self.composite_name])
                        params[self.name_field] = name
                        element_desc = ''
                        prev_catch = current_catch
                        self.elements.append(params)

    @element_classes.append
    class Tags(INPElementClass):
        inp_label = '[TAGS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('TagType', str), ('Name', str), ('Tag',  str)])
            self.defaults = {'TagType' : None, 'Name' : None, 'Tag' : None}
            self.desc_field = None
            self.sort_by = ['TagType']

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if re.match(self.pats['desc'], line) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    line = line.split(None, 2)
                    if len(line) != len(self.fields): 
                        raise self._unexpected_line_exc(line)

                    for j, value in enumerate(line):
                        if value is not None:
                            line[j] = self.fields.values()[j](value.strip())

                    params = dict(zip(self.fields.keys(), line))
                    self.elements.append(params)

    @element_classes.append
    class PatternMultipliers(INPElementClass):
        inp_label = '[PATTERNS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.inp_label = self.__class__.inp_label
            self.section = self.__class__.__name__
            self.fields = OrderedDict([('Pattern', str),
                                       ('Type', str),
                                       ('Multiplier', str)])
            self.ordinal_field = 'Ordinal'
            self.composite_name = ['Pattern', 'Type', self.ordinal_field]
            self.inp_grouping = self.name_field

            self.fmt_params = {'MONTHLY' : {'count' : 12, 'width' : 6},
                          'DAILY' : {'count' : 7, 'width' : 7},
                          'HOURLY' : {'count' : 24, 'width' : 6},
                          'WEEKEND' : {'count' : 24, 'width' : 6}}

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            new_pattern = True
            element_desc = ''
            past_header = False
            pattern_descriptions = {}
            current_mul_length = None
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if (re.match(self.pats['header'], line) and not past_header) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    past_header = True
                    if re.match(self.pats['desc'], line):
                        desc = line.strip(self.pats['desc_whitespace'])
                        element_desc = desc if not element_desc else '\n'.join([element_desc, desc])
                        continue
                    else:
                        line_descs = {'marked' : '', 'unmarked' : ''}

                        if re.search(self.pats['semicolon'], line):
                            line, line_descs['marked'] = re.split(self.pats['adj_semicolons'], line, maxsplit=1)
                            line_descs['marked'] = line_descs['marked'].strip(self.pats['desc_whitespace'])

                        line = line.split()
                        try:
                            dummy = float(line[1])
                        except:
                            new_pattern = True
                            current_mult_length = self.fmt_params[line[1]]['width']
                            expected_line_len = current_mult_length + 2
                        else:
                            new_pattern = False
                            expected_line_len = current_mult_length + 1

                        if len(line) > expected_line_len:
                            if self.long_line_comment:
                                line_descs['unmarked'] = ' '.join(line[expected_line_len:]).strip()
                                line = line[:expected_line_len]
                            else:
                                raise self._unexpected_line_exc(line)

                        if all(line_descs.values()):
                            line_desc = ' ; '.join([line_descs['unmarked'], line_descs['marked']])
                        elif line_descs['marked']:
                            line_desc = line_descs['marked']
                        elif line_descs['unmarked']:
                            line_desc = line_descs['unmarked']
                        else:
                            line_desc = ''

                        if line_desc:
                            element_desc = line_desc if not element_desc else '\n'.join([element_desc, line_desc])

                        if new_pattern:
                            pattern = line[0]
                            pattern_descriptions[pattern] = element_desc
                            pat_type = line[1]
                            current_ordinal = 1
                            for multiplier in line[2:]:
                                try:
                                    multiplier = float(multiplier)
                                except:
                                    raise self._unexpected_line_exc(line)

                                params = {'Pattern'     : pattern,
                                          'Type'        : pat_type,
                                          self.ordinal_field : current_ordinal,
                                          'Multiplier'  : float(multiplier)}

                                params[self.name_field] = ':'.join([str(params[field]) for field in self.composite_name])
                                self.elements.append(params)
                                if current_ordinal == 1:
                                    element_desc = '' # description only follows first multiplier, so reset description
                                current_ordinal += 1
                        else:
                            if element_desc:
                                current_desc = pattern_descriptions[pattern] 
                                pattern_descriptions[pattern] = current_desc + '\n' + element_desc if current_desc else element_desc
                            for multiplier in line[1:]:
                                name = ':'.join([pattern, pat_type, str(current_ordinal)])
                                params = {self.name_field : name, 
                                          'Pattern'     : pattern,
                                          'Type'        : pat_type,
                                          self.ordinal_field : current_ordinal,
                                          'Multiplier'  : float(multiplier)}
                                self.elements.append(params)
                                current_ordinal += 1

                        element_desc = ''

                for element in self.elements:
                    desc = pattern_descriptions[element['Pattern']]
                    element[self.desc_field] = desc.replace('\\n', '\n').strip()
                    #element[self.desc_field] = re.sub('\n$', '', desc, count = 1) if desc else None

        def inp_lines(self, **kwargs):
            pat_key = lambda x: (x['Pattern'], x['Type'])
            elements = []
            for pat, mults in itertools.groupby(sorted(self.elements, key=pat_key), pat_key):
                pat, pat_type = pat
                pat_type = pat_type.upper()
                mults = list(mults)
                mults = sorted(mults, key=lambda x: x[self.ordinal_field])

                if len(mults) != self.fmt_params[pat_type]['count']:
                    raise Exception("Cannot generate [PATTERNS] lines, incorrect number of multipliers for pattern type.")
                else:
                    rows = itertools.izip_longest(*[iter(mults)]*self.fmt_params[pat_type]['width'], fillvalue=None)
                    for i, row in enumerate(rows):
                        desc = row[0][self.desc_field] if not i else None
                        out_type = pat_type if not i else ''
                        row = filter(None, row)
                        mult_nums = [str(x['Multiplier']) for x in row]
                        mult_str = '  '.join(mult_nums)
                        elements.append({self.name_field : pat,
                                         self.ordinal_field : i,
                                         self.desc_field : desc,
                                         'Pattern' : pat, 
                                         'Type' : out_type, 
                                         'Multiplier' : mult_str})

            return super(PatternMultipliers, self).inp_lines(elements=elements, **kwargs)

    @element_classes.append
    class CurvePoints(INPElementClass):
        inp_label = '[CURVES]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Curve', str),
                                       ('Type', str),
                                       ('XCoordinate', float),
                                       ('YCoordinate', float)])
            self.ordinal_field = 'Ordinal' 
            self.composite_name = ['Curve', self.ordinal_field]
            self.inp_grouping = 'Curve'
            self.sort_by = ['Curve', self.ordinal_field]
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            new_curve = True
            element_desc = ''
            past_header = False
            curve_types_by_name = {}
            curve_points_by_name = {}
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if re.match(self.pats['header'], line) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    past_header = True
                    if re.match(self.pats['desc'], line):
                        past_header = True
                        desc = line.strip(self.pats['desc_whitespace'])
                        element_desc = desc if not element_desc else element_desc + '\n' + desc
                    else:
                        line_descs = {'marked' : '', 'unmarked' : ''}
                        if re.search(self.pats['semicolon'], line):
                            line, line_descs['marked'] = re.split(self.pats['adj_semicolons'], line, maxsplit=1)
                            line_descs['marked'] = line_descs['marked'].strip(self.pats['desc_whitespace'])

                        line = line.split()
                        try:
                            dummy = float(line[1])
                        except:
                            new_curve = True
                            expected_line_length = 4
                            curve_types_by_name[line[0]] = line[1]
                        else:
                            new_curve = False
                            curve_name = line[0]
                            expected_line_length = 3


                        if len(line) != expected_line_length:
                            if len(line) > expected_line_length and self.long_line_comment:
                                line_descs['unmarked'] = ' '.join(line[expected_line_length:]).strip()
                                line = line[:expected_line_length]
                            else:
                                raise self._unexpected_line_exc(line)

                        if all(line_descs.values()):
                            line_desc = ' ; '.join([line_descs['unmarked'], line_descs['marked']])
                        elif line_descs['marked']:
                            line_desc = line_descs['marked']
                        elif line_descs['unmarked']:
                            line_desc = line_descs['unmarked']
                        else:
                            line_desc = ''

                        if line_desc:
                            element_desc = line_desc if not element_desc else '\n'.join([element_desc, line_desc])

                        if new_curve:
                            #current_ordinal = 1
                            curve_types_by_name[line[0]] = line[1]
                        else:
                            if line[0] not in curve_types_by_name.keys():
                                raise Exception("Curve type for " + line[0] + " not identified.")
                            line.insert(self.fields.keys().index('Type'), curve_types_by_name[line[0]])


                        for j, value in enumerate(line):
                            line[j] = self.fields.values()[j](value)

                        params = dict(zip(self.fields.keys(), line))
                        #params[self.ordinal_field] = current_ordinal
                        #name = ':'.join([str(params[field]) for field in self.composite_name])
                        #params[self.name_field] = name
                        element_desc = element_desc.replace('\\n', '\n').strip()
                        params[self.desc_field] = element_desc
                        element_desc = ''
                        curve_points_by_name.setdefault(params['Curve'], []).append(params)
                        #self.elements.append(params)
                        #current_ordinal += 1

            for curve, points in curve_points_by_name.items():
                for i, point in enumerate(points):
                    point[self.ordinal_field] = i + 1
                    name = ':'.join([str(point[field]) for field in self.composite_name])
                    point[self.name_field] = name

                self.elements.extend(points)



        def inp_lines(self, **kwargs):
            elements = []

            curv_key = lambda x: (x['Curve'], x['Type'])
            for curv, points in itertools.groupby(sorted(self.elements, key=curv_key), curv_key):
                curv, curv_type = curv
                points = sorted(list(points), key=lambda x: x[self.ordinal_field])
                for i, point in enumerate(points):
                    if i:
                        point['Type'] = ' '*len(curv_type)
                elements.extend(points)

            return super(CurvePoints, self).inp_lines(elements=elements, **kwargs)

    @element_classes.append
    class Hydrographs(INPElementClass):
        inp_label = '[HYDROGRAPHS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label 
            self.hydro_fields = OrderedDict([('UHGroup', str),
                                             ('Month', str),
                                             ('Response', str),
                                             ('R', float),
                                             ('T', float),
                                             ('K', float),
                                             ('IAmax', float),
                                             ('IArec', float),
                                             ('IAini', float)])
            self.raingage_fields = OrderedDict([('RainGage', str), ('RainGageDescription', str)])
            self.fields = OrderedDict(self.hydro_fields.items() + self.raingage_fields.items())
            self.composite_name = ['UHGroup', 'Month', 'Response']
            self.inp_grouping = 'UHGroup'

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            raingages_by_group = {}
            raingage = None
            past_header = False
            element_desc = ''

            # function for parsing swmm4 format
            def extract_short_med_long(line):
                IAnumbers = line[11:14]
                shortterm = line[:2] + ['Short'] + line[2:5] + IAnumbers
                mediumterm = line[:2] + ['Medium'] + line[5:8] + IAnumbers
                longterm = line[:2] + ['Long'] + line[8:11] + IAnumbers
                return [shortterm, mediumterm, longterm]

            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if (re.match(self.pats['header'], line) and not past_header) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    past_header = True
                    if re.match(self.pats['desc'], line):
                        desc = line.strip(self.pats['desc_whitespace'])
                        element_desc = desc if not element_desc else '\n'.join([element_desc, desc])
                        continue
                    else:
                        line_descs = {'marked' : '', 'unmarked' : ''}

                        if re.search(self.pats['semicolon'], line):
                            line, line_descs['marked'] = re.split(self.pats['adj_semicolons'], line, maxsplit=1)
                            line_descs['marked'] = line_descs['marked'].strip(self.pats['desc_whitespace'])

                        line = line.split()
                        group = line[0]
                        rg_name_idx = 1
                        response_idx = 2
                        num_params_in_rg_line = 2
                        is_rg_line = len(line) == num_params_in_rg_line
                        if self.long_line_comment and len(line) > num_params_in_rg_line:
                            is_rg_line = line[response_idx].lower() not in ('short', 'medium', 'long')

                        if is_rg_line:
                            if len(line) > 2:
                                if self.long_line_comment:
                                    line_descs['unmarked'] = ' '.join(line[rg_name_idx+1:]).strip()
                                    line = line[:rg_name_idx+1]
                                else:
                                    raise self._unexpected_line_exc(line)

                            if all(line_descs.values()):
                                line_desc = ' ; '.join([line_descs['unmarked'], line_descs['marked']])
                            elif line_descs['marked']:
                                line_desc = line_descs['marked']
                            elif line_descs['unmarked']:
                                line_desc = line_descs['unmarked']
                            else:
                                line_desc = ''

                            if line_desc:
                                element_desc = line_desc if not element_desc else '\n'.join([element_desc, line_desc])

                            element_desc = element_desc.replace('\\n', '\n').strip()
                            raingages_by_group[group] = {'RainGage' : line[rg_name_idx], 
                                                         'RainGageDescription' : element_desc}
                        else:
                            # first condition applies to SWMMR 4 hydrograph format
                            if len(line) == 14:
                                element_lines = extract_short_med_long(line)
                            elif len(line) == 9:
                                element_lines = [line]
                            elif self.long_line_comment and len(line) > 9:
                                try:
                                    [float(x) for x in line[9:14]]
                                except:
                                    element_lines = [line[:9]]
                                    line_descs['unmarked'] = ' '.join(line[9:]).strip()
                                else:
                                    element_lines = extract_short_med_long(line[:14])
                                    line_descs['unmarked'] = ' '.join(line[14:]).strip()
                            else:
                                raise self._unexpected_line_exc(line)

                            if all(line_descs.values()):
                                line_desc = ' ; '.join([line_descs['unmarked'], line_descs['marked']])
                            elif line_descs['marked']:
                                line_desc = line_descs['marked']
                            elif line_descs['unmarked']:
                                line_desc = line_descs['unmarked']
                            else:
                                line_desc = ''

                            if line_desc:
                                element_desc = line_desc if not element_desc else '\n'.join([element_desc, line_desc])

                            element_desc = element_desc.replace('\\n', '\n').strip()

                            for line in element_lines:
                                if len(line) == len(self.hydro_fields):
                                    for j, value in enumerate(line):
                                        if value is not None:
                                            line[j] = self.hydro_fields.values()[j](value)

                                    params = dict(zip(self.hydro_fields.keys(), line))
                                    params[self.name_field] = ':'.join([params['UHGroup'],
                                                               params['Month'],
                                                               params['Response']])
                                    params[self.desc_field] = element_desc
                                    #params[self.desc_field] = re.sub('\n$', '', element_desc, count = 1) \
                                    #       if element_desc else None
                                    self.elements.append(params)
                                else:
                                    raise self._unexpected_line_exc(line)

                        element_desc = ''

            for element in self.elements:
                if element['UHGroup'] in raingages_by_group.keys():
                    raingage = raingages_by_group[element['UHGroup']]
                    for field in self.raingage_fields.keys():
                        element[field] = raingage[field]
                else:
                    raise Exception('get_Hydrographs: Missing raingage for ' + element['UHGroup'])

        def inp_lines(self, **kwargs):
            months_ordering = ['All', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            response_ordering = ['Short', 'Medium', 'Long']
            key = lambda x: (x['UHGroup'], months_ordering.index(x['Month'].title()), response_ordering.index(x['Response']))
            current_uh_group = None
            remove_fields = ['RainGage', 'RainGageDescription']
            alt_fields = [name for name in self.fields.keys() if name not in remove_fields]
            alt_fields[alt_fields.index('Month')] = 'Month/RG'
            elements = []

            sorted_elements = sorted(self.elements, key=key)

            for element in sorted_elements:
                element = copy.deepcopy(element)
                uh_group = element['UHGroup']
                if uh_group != current_uh_group:
                    rg_row = dict((name, None) for name in alt_fields)
                    rg_row = {'UHGroup' : element['UHGroup'], 
                              'Month/RG' : element['RainGage'],
                              self.desc_field : element['RainGageDescription'],
                              self.name_field : element['UHGroup']}
                    for name in alt_fields:
                        if name not in rg_row.keys():
                            rg_row[name] = None
                    elements.append(rg_row)
                    current_uh_group = uh_group
                element['Month/RG'] = element['Month']
                for name in remove_fields + ['Month']:
                    del element[name]
                elements.append(element)

            return super(Hydrographs, self).inp_lines(elements=elements, fieldnames=alt_fields, **kwargs)

    @element_classes.append
    class SnowPacks(INPElementClass):
        inp_label = '[SNOWPACKS]' 
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Name', str),
                                       ('PlowMinCoeff', float),
                                       ('PlowMaxCoeff', float),
                                       ('PlowBaseTemp', float),
                                       ('PlowFFH2OCap', float),
                                       ('PlowInitDepth', float),
                                       ('PlowInitFreeH2O', float),
                                       ('PlowImpAreaFrac', float),
                                       ('ImpvMinCoeff', float),
                                       ('ImpvMaxCoeff', float),
                                       ('ImpvBaseTemp', float),
                                       ('ImpvFFH2OCap', float),
                                       ('ImpvInitDepth', float),
                                       ('ImpvInitFreeH2O', float),
                                       ('ImpvTCDepth', float),
                                       ('PervMinCoeff', float),
                                       ('PervMaxCoeff', float),
                                       ('PervBaseTemp', float),
                                       ('PervFFH2OCap', float),
                                       ('PervInitDepth', float),
                                       ('PervInitFreeH2O', float),
                                       ('PervTCDepth', float),
                                       ('RmvlStartDepth', float),
                                       ('H2OshedExitFrac', float),
                                       ('Trans_to_ImpvFrac', float),
                                       ('Trans_to_PervFrac', float),
                                       ('MeltFrac', float),
                                       ('Trans_to_SubctchFrac', float),
                                       ('RmvlName', str)])

            self.inp_grouping = self.name_field
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            fields = self.fields.keys()
            dtypes = self.fields.values()
            fields_by_catchtype = {'PLOWABLE' : fields[1:8], 'IMPERVIOUS' : fields[8:15], 
                'PERVIOUS' : fields[15:22], 'REMOVAL' : fields[22:29]}
            dtypes_by_catchtype = {'PLOWABLE' : dtypes[1:8], 'IMPERVIOUS' : dtypes[8:15], 
                'PERVIOUS' : dtypes[15:22], 'REMOVAL' : dtypes[22:29]}
            element_desc = ''
            past_header = False
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if (re.match(self.pats['header'], line) and not past_header) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    past_header = True
                    if re.match(self.pats['desc'], line):
                        desc = line.strip(self.pats['desc_whitespace'])
                        element_desc = desc if not element_desc else '\n'.join([element_desc, desc])
                        continue
                    else:
                        line_descs = {'marked' : '', 'unmarked' : ''}

                        if re.search(self.pats['semicolon'], line):
                            line, line_descs['marked'] = re.split(self.pats['adj_semicolons'], line, maxsplit=1)
                            line_descs['marked'] = line_descs['marked'].strip(self.pats['desc_whitespace'])

                        line = line.split()

                        min_params_in_removal_line = 8
                        category_idx = 1
                        if len(line) != 9:
                            if line[category_idx] == 'REMOVAL':
                                if len(line) == min_params_in_removal_line:
                                    line.append('')
                                if len(line) >= min_params_in_removal_line:
                                    if self.long_line_comment:
                                        raise self._ambiguous_line_exc(line)
                                    else:
                                        raise self._unexpected_line_exc(line)
                                elif len(line) == min_params_in_removal_line:
                                    line.append('')
                                else:
                                    raise self._unexpected_line_exc(line)
                            elif len(line) > 9 and self.long_line_comment:
                                line_descs['unmarked'] = ' '.join(line[9:]).strip()
                                line = line[:9]
                            else:
                                raise self._unexpected_line_exc(line)

                        if all(line_descs.values()):
                            line_desc = ' ; '.join([line_descs['unmarked'], line_descs['marked']])
                        elif line_descs['marked']:
                            line_desc = line_descs['marked']
                        elif line_descs['unmarked']:
                            line_desc = line_descs['unmarked']
                        else:
                            line_desc = ''

                        if line_desc:
                            element_desc = line_desc if not element_desc else '\n'.join([element_desc, line_desc])

                        catchtype_colnum = 1
                        current_catchtype = line[catchtype_colnum]

                        current_fields = fields_by_catchtype[current_catchtype]
                        current_dtypes = dtypes_by_catchtype[current_catchtype]

                        current_parameters = line[(catchtype_colnum + 1):]
                        current_parameters = [dtype(current_parameters[j]) for j, dtype in enumerate(current_dtypes)]

                        name_colnum = 0
                        current_name = line[name_colnum]

                        has_element = False
                        element_desc = element_desc.replace('\\n', '\n')
                        for element in self.elements:
                            if element[self.name_field] == current_name:
                                has_element = True
                                for j, field in enumerate(current_fields):
                                    element[field] = current_parameters[j]
                                if element['Description'] and element_desc:
                                    element['Description'] = element['Description'] + '\n' + element_desc
                                elif element_desc:
                                    element['Description'] = element_desc
                                element_desc = ''
                                break

                        if not has_element:
                            element = dict(zip(fields, [None for j in range(len(fields))]))
                            element[self.name_field] = current_name
                            for j, field in enumerate(current_fields):
                                element[field] = current_parameters[j]
                            element[self.desc_field] = element_desc
                            self.elements.append(element)
                            element_desc = ''

        def inp_lines(self, **kwargs):
            alt_fields = ['Name', 'CatchmentType', 'Param1', 'Param2', 'Param3', 'Param4', 'Param5', 'Param6', 'Param7']

            elements = []
            prefixes = ['Plow', 'Impv', 'Perv', 'Rmvl']
            fieldnames = self.fields.keys()
            sp_dict = {0:'PLOWABLE', 1:'IMPERVIOUS', 2:'PERVIOUS', 3:'REMOVAL'}
            for element in self.elements:
                desc_added = False
                for i in range(4):
                    new_element = []
                    for field in fieldnames[i*7+1:(i+1)*7+1]:
                        new_element.append(element[field])
                    if any(new_element):
                        new_row = tuple([element[self.name_field]] + [sp_dict[i]] + new_element) 
                        if not desc_added:
                            new_row = new_row + (element[self.desc_field].strip('\\n'), )
                            desc_added = True
                        else:
                            new_row = new_row + (None, )
                        elements.append(dict(zip(alt_fields + [self.desc_field], new_row)))

            return super(SnowPacks, self).inp_lines(elements=elements, fieldnames=alt_fields, **kwargs)
            
    @element_classes.append
    class TimeSeriesPoints(INPElementClass):
        inp_label = '[TIMESERIES]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('TimeSeries', str),
                                       ('FileName', str),
                                       ('DateTime', str),
                                       ('Duration', float),
                                       ('Value', float)])
            self.files = {}
            self.md5_field = 'FileMD5'
            self.ordinal_field = 'Ordinal'
            self.inp_grouping = 'TimeSeries'
            self.composite_name = ['TimeSeries', self.ordinal_field]
            self.sort_by = ['TimeSeries']

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            element_desc = ''
            current_series = None
            past_header = False
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if (re.match(self.pats['header'], line) and not past_header) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    past_header = True
                    if re.match(self.pats['desc'], line):
                        line = line.strip(self.pats['desc_whitespace'])
                        element_desc = line if not element_desc else element_desc + '\n' + line
                        continue
                    else:
                        line_descs = {'marked' : '', 'unmarked' : ''}

                        if re.search(self.pats['semicolon'], line):
                            line, line_descs['marked'] = re.split(self.pats['adj_semicolons'], line, maxsplit=1)
                            line_descs['marked'] = line_descs['marked'].strip(self.pats['desc_whitespace'])

                        original_line = line
                        line = line.split()
                        series = line[0]
                        if series != current_series:
                            new_series = True
                            current_series = series
                            current_ordinal = 1

                        if line[1] == 'FILE' and len(line) > 3:
                            if self.long_line_comment:
                                has_quote = False
                                comment_start = False
                                for j in range(2, len(line)):
                                    val = line[j]
                                    if j == 2:
                                        found_first_quote = re.match('^\'|"', val)
                                        if found_first_quote:
                                            has_quote = True
                                            quote_char = found_first_quote.group()
                                            found_second_quote = re.search("'|\"$", val)
                                            if found_second_quote:
                                                comment_start = j + 1
                                                break
                                    else:
                                        if has_quote and re.search('\'|"$', val):
                                            comment_start = j + 1
                                            break

                                if comment_start:
                                    line_descs['unmarked'] = ' '.join(line[comment_start:]).strip()
                                    line = line[:2]
                                    line.append(quote_char + original_line.split(quote_char)[1] + quote_char)
                            else:
                                quote_char = re.match('^"|\'', line[2]).group()
                                line = line[:2]
                                line.append(quote_char + original_line.split(quote_char)[1] + quote_char)

                        fields = self.fields.keys()
                        if len(line) == 3:
                            if 'FILE' in line:
                                line.remove('FILE')
                                line.extend([None, None, None])
                            else:
                                line.insert(fields.index('FileName'), None)
                                line.insert(fields.index('DateTime'), None)
                        else:
                            dtime = ' '.join(line[1:3])
                            line[1] = dtime
                            line = line[:2] + line[3:]
                            line.insert(fields.index('FileName'), None)
                            line.insert(fields.index('Duration'), None)

                        if len(line) != len(self.fields):
                            if len(line) > len(self.fields) and self.long_line_comment:
                                line_descs['unmarked'] = ' '.join(line[len(self.fields):]).strip()
                                line = line[:len(self.fields)]
                            else:
                                raise self._unexpected_line_exc(line)

                        if all(line_descs.values()):
                            line_desc = ' ; '.join([line_descs['unmarked'], line_descs['marked']])
                        elif line_descs['marked']:
                            line_desc = line_descs['marked']
                        elif line_descs['unmarked']:
                            line_desc = line_descs['unmarked']
                        else:
                            line_desc = ''

                        if line_desc:
                            element_desc = line_desc if not element_desc else '\n'.join([element_desc, line_desc])

                        line = [self.fields.values()[j](value) if value else value for j, value in enumerate(line)]
                        params = dict(zip(fields, line))
                        params[self.ordinal_field] = current_ordinal
                        params[self.name_field] = ':'.join([str(params[field]) for field in self.composite_name])
                        params[self.desc_field] = element_desc.replace('\\n', '\n').strip()
                        if params['FileName'] is not None and self.require_support_files:
                            filepath = params['FileName'].strip(' \t\n"\'')
                            if not os.path.exists(filepath):
                                filepath = os.path.join(os.path.dirname(self.inp_path), filepath)

                            if not os.path.exists(filepath):
                                fname = params['FileName']
                                raise Exception("Can't find support file '" + fname + "' referenced in [TIMESERIES]")
                            else:
                                params['FileName'] = '"' + os.path.basename(filepath) + '"'
                                with open(filepath, 'rb') as f:
                                    fcontents = f.read()
                                md5 = hashlib.md5(fcontents).hexdigest()
                                params['FileMD5'] = md5
                                self.files[filepath] = md5
                        else:
                            params['FileMD5'] = None

                        element_desc = ''
                        self.elements.append(params)
                        current_ordinal += 1

        def inp_lines(self, **kwargs):
            elements = [] 
            key = lambda x: (x['TimeSeries'], x[self.ordinal_field])
            for ts, points in itertools.groupby(sorted(self.elements, key=key), lambda x: x['TimeSeries']):
                points = copy.deepcopy(list(points))
                if len(points) == 1 and points[0]['FileName']:
                    point = points[0]
                    point['FileName'] = 'FILE  ' + point['FileName']
                    elements.append(point)
                else:
                    for point in points:
                        if isinstance(point['DateTime'], datetime.datetime):
                            point['DateTime'] = point['DateTime'].strftime(format='%m/%d/%Y %H:%M:%S')
                        elements.append(point)
            alt_fields = self.fields.keys()
            del alt_fields[alt_fields.index('FileName')]
            alt_fields.append('FileName')
            return super(TimeSeriesPoints, self).inp_lines(elements=elements, fieldnames=alt_fields, **kwargs)

    @element_classes.append
    class Controls(INPElementClass):
        inp_label = '[CONTROLS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('RuleName', str),
                                       ('RuleText', str)])

            self.ordinal_field = 'Ordinal'
            self.composite_name = [self.ordinal_field, 'RuleName']
            self.sort_by = [self.ordinal_field]

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            current_rule = None
            last_description = ''
            current_description = ''
            current_ordinal = 0
            
            def normalize_rule_text(rule_text):
                rule = re.sub(' +', ' ', re.sub('\n|\t', ' ', rule_text)).strip()
                object_names = ['pump', 'node', 'orifice', 'weir', 'outlet', 'link', 'simulation']
                parameter_names = ['status', 'setting', 'on', 'off', 'depth', 'head', 'inflow', 'flow',
                                   'time', 'date', 'month', 'day', 'clocktime']
                logical_names = ['if', 'then', 'and', 'or', 'priority']
                modulated_names = ['curve', 'timeseries', 'pid']
                words_to_cap = object_names + parameter_names + logical_names + modulated_names
                cap_pat = re.compile(r'\b(' + '|'.join(words_to_cap) + r')\b', re.IGNORECASE)
                return re.sub(cap_pat, lambda m: m.group(1).upper(), rule)

            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if i == (self.end_lineno - 1) and current_rule is not None:
                    desc = current_description.replace('\\n', '\n').strip()
                    element = {'RuleName' : current_rule_name,
                               self.ordinal_field: current_ordinal,
                               'RuleText' : normalize_rule_text(current_rule),
                               self.desc_field : desc
                              }
                              # self.desc_field : re.sub('\n$', '', current_description, count = 1) \
                              #                 if current_description else ''
                    element[self.name_field] = ':'.join([str(element[field]) for field in self.composite_name])
                    self.elements.append(element)
                elif re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    line_split = line.split(None, 2)
                    if re.match('rule', line_split[0].strip(), re.IGNORECASE):
                        if current_rule is not None:
                            name = ':'.join([str(current_ordinal), current_rule_name])
                            desc = current_description.replace('\\n', '\n').strip()
                            self.elements.append({self.name_field: name,
                                             'RuleName' : current_rule_name,
                                             'Ordinal' : current_ordinal,
                                             'RuleText' : normalize_rule_text(current_rule),
                                             self.desc_field : desc})
                                             #self.desc_field : re.sub('\n$', '', current_description, count=1) \
                                             #                if current_description else ''})
                        current_ordinal += 1
                        current_rule_name = line_split[1]
                        current_rule = '' if len(line_split) == 2 else line_split[2]
                        if last_description != '':
                            current_description = last_description
                            current_description = filter(lambda c: c not in ";", current_description)
                            last_description = ''
                        else:
                            current_description = ''
                    elif re.match(self.pats['desc'], line):
                        last_description += line
                    else:
                        if last_description != '':
                            current_description += last_description.strip(';')
                            last_description = ''

                        current_rule += line

        def inp_lines(self, **kwargs):
            elements = sorted(self.elements, key=lambda x: x[self.ordinal_field])
            lines = [self.inp_label]
            for row in elements:
                rule_name = row['RuleName']
                description = row[self.desc_field]
                if description and not kwargs.get('exclude_descs', False):
                    description = description.decode('string-escape')
                    #description = description.strip('\n')
                    description = description.split('\n')
                    description = [';' + line for line in description]
                    lines.extend(description)

                lines.append('{:<9}'.format('RULE') + rule_name)
                rule_text = row['RuleText']
                logical_names = ['IF', 'THEN', 'AND', 'OR', 'PRIORITY']

                rule_text = re.sub(r'\b(' + '|'.join(logical_names) + r')\b', lambda m: '\n' + m.group(1), rule_text).strip()
                rule_text = rule_text.decode('string-escape')
                rule_text = rule_text.split('\n')
                rule_text = [line.split(None, 1) for line in rule_text]
                andorpat = re.compile('and|or', re.IGNORECASE)
                rule_text = ['{:>8} {}'.format(*line) if re.match(andorpat, line[0]) else '{:<9}{}'.format(*line) 
                             for line in rule_text]
                for line in rule_text:
                    lines.append(line)
                lines.append('')

            return lines    
    
    @element_classes.append
    class TransectPoints(INPElementClass):
        inp_label = '[TRANSECTS]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('TransectName', str),
                                       ('StationCount', int),
                                       ('LeftBankRoughness', float),
                                       ('RightBankRoughness', float),
                                       ('ChannelRoughness', float),
                                       ('LeftBankStation', float),
                                       ('RightBankStation', float),
                                       ('StationsModifier', float),
                                       ('ElevationsModifier', float),
                                       ('MeanderModifier', float),
                                       ('Description', str),
                                       ('Station_ft', float),
                                       ('Elevation_ft', float)])
            self.ordinal_field = 'Ordinal' 
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            element_desc = ''
            current_leftroughness = None
            past_header = False
            current_elements = []
            count = 0
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if (re.match(self.pats['header'], line) and not past_header) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    past_header=True
                    if re.match(self.pats['desc'], line):
                        line = line.strip(self.pats['desc_whitespace'])
                        element_desc = line if not element_desc else element_desc + '\n' + line
                        continue
                    else:
                        line_descs = {'marked' : '', 'unmarked' : ''}
                        if re.search(self.pats['semicolon'], line):
                            line, line_descs['marked'] = re.split(self.pats['adj_semicolons'], line, maxsplit=1)
                            line_descs['marked'] = line_descs['marked'].strip(self.pats['desc_whitespace'])

                        line = line.split()

                        line_marker = line[0]
                        if line_marker == 'NC':
                            if current_elements:
                                self.elements.extend(current_elements)
                                del current_elements[:]

                            num_fields_NC = 4
                            if len(line) != num_fields_NC:
                                if len(line) > num_fields_NC and self.long_line_comment:
                                    line_descs['unmarked'] = ' '.join(line[num_fields_NC:]).strip()
                                    line = line[:num_fields_NC]
                                else:
                                    raise self._unexpected_line_exc(line)

                            if all(line_descs.values()):
                                line_desc = ' ; '.join([line_descs['unmarked'], line_descs['marked']])
                            elif line_descs['marked']:
                                line_desc = line_descs['marked']
                            elif line_descs['unmarked']:
                                line_desc = line_descs['unmarked']
                            else:
                                line_desc = ''

                            if line_desc:
                                element_desc = line_desc if not element_desc else '\n'.join([element_desc, line_desc])

                            current_description = element_desc
                            element_desc = ''
                            leftroughness = float(line[1])
                            rightroughness = float(line[2])
                            channelroughness = float(line[3])
                            current_ordinal = 1
                        elif line_marker == 'X1':
                            num_fields_X1 = 10
                            if len(line) != num_fields_X1:
                                if len(line) > num_fields_X1 and self.long_line_comment:
                                    line_descs['unmarked'] = ' '.join(line[num_fields_X1:]).strip()
                                    line = line[:num_fields_X1]
                                else:
                                    raise self._unexpected_line_exc(line)

                            if all(line_descs.values()):
                                line_desc = ' ; '.join([line_descs['unmarked'], line_descs['marked']])
                            elif line_descs['marked']:
                                line_desc = line_descs['marked']
                            elif line_descs['unmarked']:
                                line_desc = line_descs['unmarked']
                            else:
                                line_desc = ''

                            if line_desc:
                                element_desc = line_desc if not element_desc else '\n'.join([element_desc, line_desc])

                            if element_desc:
                                current_description = element_desc if not current_description  \
                                                      else current_description +'\n'+ element_desc
                                element_desc = ''
                            transectname = line[1]
                            numstations = int(line[2])
                            left_bankstation = float(line[3])
                            right_bankstation = float(line[4])
                            meander_mod = float(line[7])
                            station_mod = float(line[8])
                            elev_mod = float(line[9])
                        elif line_marker == 'GR':
                            if self.long_line_comment:
                                end_of_parameters = len(line)
                                for i, x in enumerate(line):
                                    if i:
                                        try:
                                            _ = float(x)
                                        except:
                                            end_of_parameters = i
                                            break

                                if end_of_parameters != len(line):
                                    line_descs['unmarked'] = ' '.join(line[end_of_parameters:]).strip()
                                    line = line[:end_of_parameters]

                            if (len(line) % 2) != 1:
                                raise self._unexpected_line_exc(line)

                            if all(line_descs.values()):
                                line_desc = ' ; '.join([line_descs['unmarked'], line_descs['marked']])
                            elif line_descs['marked']:
                                line_desc = line_descs['marked']
                            elif line_descs['unmarked']:
                                line_desc = line_descs['unmarked']
                            else:
                                line_desc = ''

                            if line_desc:
                                element_desc = line_desc if not element_desc else '\n'.join([element_desc, line_desc])

                            if element_desc:
                                current_description = element_desc if not current_description \
                                                      else current_description + '\n' + element_desc
                                element_desc = ''

                            line = line[1:]
                            for i in range(0, len(line), 2):
                                desc = current_description.replace('\\n', '\n').strip()
                                if current_elements:
                                    for element in current_elements:
                                        element['Description'] = desc

                                element = {'Name'               : ':'.join([transectname, str(current_ordinal)]),
                                           'TransectName'       : transectname,
                                           self.ordinal_field   : current_ordinal,
                                           'StationCount'       : numstations,
                                           'LeftBankRoughness'  : leftroughness,
                                           'RightBankRoughness' : rightroughness,
                                           'ChannelRoughness'   : channelroughness,
                                           'LeftBankStation'    : left_bankstation,
                                           'RightBankStation'   : right_bankstation,
                                           'StationsModifier'   : station_mod,
                                           'ElevationsModifier' : elev_mod,
                                           'MeanderModifier'    : meander_mod,
                                           self.desc_field      : desc,
                                           'Elevation_ft'       : float(line[i]),
                                           'Station_ft'         : float(line[i+1])
                                           }
                                current_ordinal += 1
                                current_elements.append(element)

            if current_elements:
                self.elements.extend(current_elements)
    
        def inp_lines(self, **kwargs):
            lines = [self.inp_label]
            
            nc_names = ['LeftBankRoughness', 'RightBankRoughness', 'ChannelRoughness']
            x1_left_names = ['TransectName', 'StationCount', 'LeftBankStation', 'RightBankStation']
            x1_right_names = ['MeanderModifier', 'StationsModifier', 'ElevationsModifier']
            x1_num_filler_zeros = 2
            
            currentline_point_count = 0
            stations_written = 0
            total_station_count = 0

            col_fwf = '{:<7}'
            for transect, gr_points in itertools.groupby(self.elements, lambda x: x['TransectName']):
                gr_points = sorted(list(gr_points), key=lambda x: x[self.ordinal_field])
                if len(lines) > 1:
                    lines.append('')

                gr_point = gr_points[0]
                desc = gr_point[self.desc_field]
                if desc and not kwargs.get('exclude_descs', False):
                    desc = desc.decode('string-escape')
                    desc = desc.split('\n')
                    desc = ['; ' + line for line in desc]
                    lines.extend(desc)

                nc_line = ['NC'] + [col_fwf.format(str(gr_point[name])) for name in nc_names]
                spacer = ' ' * 5
                nc_line = spacer.join(nc_line)
                lines.append(nc_line)

                x1_line = ['X1'] + [col_fwf.format(str(gr_point[x1_left_names[0]])), col_fwf.format('')] + \
                          [col_fwf.format(str(gr_point[name])) for name in x1_left_names[1:]] + \
                          [col_fwf.format('0') for i in xrange(x1_num_filler_zeros)] + \
                          [col_fwf.format(str(gr_point[name])) for name in x1_right_names]
                x1_line = spacer.join(x1_line)
                lines.append(x1_line)

                num_tpoints_per_line = 5
                point_rows = itertools.izip_longest(*[iter(gr_points)]*num_tpoints_per_line, fillvalue=None)

                for row in point_rows:
                    row = filter(None, row)
                    pnts = [[col_fwf.format(str(x)) for x in [point['Elevation_ft'], point['Station_ft']]] for point in row]
                    lines.append(spacer.join(reduce(lambda x,y: x+y, pnts, ['GR'])))

            return lines

    @element_classes.append
    class Report(INPElementClass):
        inp_label = '[REPORT]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('INPUT', str),
                                       ('CONTROLS', str),
                                       ('SUBCATCHMENTS', str),
                                       ('NODES', str),
                                       ('LINKS', str)])
            self.name_field = None
            self.desc_field = None

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            report = {} 
            links = []
            nodes = []
            catchments = []
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if re.match(self.pats['desc'], line) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    line = line.split(None, 1)
                    if len(line) != 2:
                        raise self._unexpected_line_exc(line)
                    param = line[0].strip().upper()
                    value = line[1].strip()
                    link_pat = re.compile('^link', re.IGNORECASE)
                    node_pat = re.compile('^node', re.IGNORECASE)
                    catch_pat = re.compile('^subcatchments', re.IGNORECASE)

                    if re.search(link_pat, param):
                        links.extend(value.split())
                    elif re.search(node_pat, param):
                        nodes.extend(value.split())
                    elif re.search(catch_pat, param):
                        catchments.extend(value.split())
                    else:
                        report[param] = self.fields[param](value)

            report['LINKS'] = ' '.join(links) if links else None
            report['NODES'] = ' '.join(nodes) if nodes else None
            report['SUBCATCHMENTS'] = ' '.join(catchments) if catchments else None

            if all([value is None for value in report.values()]):
                self.elements = []
            else:
                self.elements = [report]

        def inp_lines(self, **kwargs):
            row = self.elements[0]
            lines = ['' for i in xrange(len(self.fields) + 1)]
            label_col_width = max([len(field) for field in self.fields.keys()])
            format_str = '{:<' + str(label_col_width) + '}'
            lines[0] = self.inp_label
            for i, field in enumerate(self.fields.keys()):
                value = row[field]
                line = format_str.format(field) + ' ' * 7 + str(value)
                lines[i + 1] = line
            return lines 

    @element_classes.append
    class Maps(INPElementClass):
        inp_label = '[MAP]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('LLXCoordinate', float),
                                       ('LLYCoordinate', float),
                                       ('URXCoordinate', float), 
                                       ('URYCoordinate', float),
                                       ('Units', str)])

            self.name_field = None
            self.desc_field = None

            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            map_opts = {}
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if re.match(self.pats['desc'], line) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    line = line.split(None, 1)
                    if len(line) != 2:
                        raise self._unexpected_line_exc(line)
                    elif re.match('dimensions', line[0], re.IGNORECASE):
                        dims = line[1].split()
                        if len(dims) != 4:
                            raise self._unexpected_line_exc(line)
                        else:
                            dims = [float(dim) for dim in dims]
                            map_opts['LLXCoordinate'] = dims[0]
                            map_opts['LLYCoordinate'] = dims[1]
                            map_opts['URXCoordinate'] = dims[2]
                            map_opts['URYCoordinate'] = dims[3]
                    elif re.match('units', line[0], re.IGNORECASE):
                        map_opts['Units'] = line[1].strip()
                    else:
                        raise self._unexpected_line_exc(line)

            if not map_opts:
                self.elements = []
            else:
                self.elements = [map_opts]

        def inp_lines(self, **kwargs):
            row = self.elements[0]
            lines = ['' for i in xrange(3)]
            lines[0] = self.inp_label
            dim_names = ['LLXCoordinate', 'LLYCoordinate', 'URXCoordinate', 'URYCoordinate']
            dims = [str(row[dim_name]) for dim_name in dim_names]
            dims_line = ' '.join(['DIMENSIONS'] + dims)
            lines[1] = dims_line
            lines[2] = 'Units      ' + row['Units']
            return lines

    @element_classes.append
    class Profiles(INPElementClass):
        inp_label = '[PROFILES]'
        def __init__(self, start_lineno=None, end_lineno=None):
            INPElementClass.__init__(self, start_lineno, end_lineno)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
            self.fields = OrderedDict([('Profile', str), ('Link', str)])
            self.desc_field = None
            self.ordinal_field = 'Ordinal'
            self.inp_grouping = 'Profile'
            
            if start_lineno is not None and end_lineno is not None:
                self.parse()

        def parse(self):
            last_profile = ''
            for i in range(self.start_lineno, self.end_lineno):
                line = self.getline(i)
                if re.match(self.pats['desc'], line) or re.match(self.pats['blank_or_tag'], line):
                    continue
                else:
                    line = line.split()
                    if line[0].strip()[0] == '"':
                        item_indx = 1
                        name = ''
                        for j, item in enumerate(line):
                            name += item + ' '
                            if re.search('"$', item):
                                second_quote_index = j
                                break

                        new_line = [name.strip()] + line[(second_quote_index + 1):]
                        line = new_line
                    else:
                        line[0] = '"' + line[0] + '"'

                    if len(line) != 6:
                        if len(line) < 2 or len(line) > 6:
                            raise self._unexpected_line_exc(line)

                    current_profile = line[0]
                    if current_profile != last_profile:
                        last_profile = current_profile
                        current_ordinal = 1

                    for link in line[1:]:
                        element = {self.name_field       : ':'.join([current_profile, str(current_ordinal)]),
                                   'Profile'    : current_profile,
                                   'Link'       : link,
                                   self.ordinal_field : current_ordinal}
                        current_ordinal += 1
                        self.elements.append(element)

        def inp_lines(self, **kwargs):
            key = lambda x: (x['Profile'], x[self.ordinal_field])
            elements = sorted(self.elements, key=key)

            profile_names = [row['Profile'] for row in self.elements]
            profile_names = sorted(list(set(profile_names)))

            formatted_table = []
            for profile in profile_names:
                sub_table = [row for row in elements if row['Profile'] == profile]
                sub_table = sorted(sub_table, key = lambda x: x[self.ordinal_field])

                current_link_str = ''
                num_links_per_line = 5
                subtable_len = len(sub_table)
                for i, row in enumerate(sub_table):
                    if not re.search('^"', profile):
                        profile_name = '"' + profile + '"'
                    else:
                        profile_name = profile

                    if i > 0 and (i % num_links_per_line) == 0:
                        formatted_table.append([profile_name, current_link_str])
                        current_link_str = row['Link'] + ' '
                        if i == (subtable_len -1):
                            formatted_table.append([profile_name, current_link_str])
                    elif i == (subtable_len - 1):
                        current_link_str += row['Link']
                        formatted_table.append([profile_name, current_link_str])
                    else:
                        current_link_str += row['Link'] + ' '

            new_colnames = ['Profile', 'Links']
            formatted_table = [dict((col, val) for col, val in zip(new_colnames, row)) for row in formatted_table]
            for i, row in enumerate(formatted_table):
                row[self.name_field] = row['Profile']
                row[self.ordinal_field] = i

            return super(Profiles, self).inp_lines(elements=formatted_table, fieldnames=new_colnames, **kwargs)

    @element_classes.append
    class NodeInflows(CompositeElementClass):
        inp_label = None
        def __init__(self, Inflows=Inflows(), DWF=DWF()):
            CompositeElementClass.__init__(self, Inflows=Inflows, DWF=DWF)
            self.section = self.__class__.__name__
            self.inp_label = self.__class__.inp_label
                
    return element_classes

class INP(object):
    def __init__(self, inp_path=None, new=False, require_support_files=False, long_line_comment=False, 
            recognize_subclasses=False, recognize_composite_classes=False):

        self.inp_path = inp_path
        if inp_path:
            self.inp_path = os.path.abspath(str(inp_path))
        self.new = new
        self.long_line_comment = long_line_comment
        self.require_support_files = require_support_files

        inp_path_exists = os.path.isfile(self.inp_path)
        if not new and not inp_path_exists:
            raise Exception("No such INP file: " + self.inp_path)

        self.element_classes = get_element_classes(inp_path=inp_path,
                                                   long_line_comment=long_line_comment, 
                                                   require_support_files=require_support_files)
        if not self.new:
            current_label = None
            current_label_lineno = 0
            label_pattern = re.compile('^[\s]*\[')
            current_lineno = 0
            with open(self.inp_path, 'r') as f:
                for current_lineno, line in enumerate(f.readlines()):
                    if re.match(label_pattern, line):
                        if current_label:
                            # note, line numbers are +1 because linecache.getline counts from 1
                            self.element_classes.initialize_class(current_label, current_label_lineno+1, current_lineno+1)
                        current_label_lineno = current_lineno
                        current_label = line

            if current_label:
                self.element_classes.initialize_class(current_label, current_label_lineno+1, current_lineno + 2)

            if recognize_subclasses:
                self.element_classes.merge_subclasses()

            if recognize_composite_classes:
                self.element_classes.merge_composite_classes()
        
    def set_path(self, path):
        if self.new:
            self.inp_path = path
        else:
            raise Exception("Can't change path of existing *.inp")

    def original_inp(self):
        if not self.new:
            with open(self.inp_path, 'r') as f:
                return f.read()

    def get_files(self):
        return self.element_classes.get_files()
    
    def get_inp_text(self, exclude_descs=False, eol_descs=False):
        return self.element_classes.get_inp_text(exclude_descs=exclude_descs, eol_descs=eol_descs)

    def write_inp(self, exclude_descs=False, eol_descs=False):
        if self.new:
            self.element_classes.write_inp(exclude_descs=exclude_descs, eol_descs=eol_descs)

    def as_xml(self):
        xml = '<?xml version="1.0"?>\n<INP>\n'
        for obj in self.element_classes.get_all_objects().values():
            xml += obj.as_xml()
        xml += '</INP>'

        return xml

    def add_elements(self, name, elements, recognize_subclasses=False):
        self.element_classes.add_elements(name, elements, recognize_subclasses=recognize_subclasses)
    
    def get_elements(self, name):
        return self.element_classes.get_elements(name)

    def get_object_names(self):
        return self.element_classes.get_object_names()

    def merge_subclasses(self):
        self.element_classes.merge_subclasses()

    def merge_composite_classes(self):
        self.element_classes.merge_composite_classes()

    def add_meta_data(self, data):
        self.element_classes.add_meta_data(data)

    def get_class_names(self):
        return self.element_classes.get_object_names()

    def get_supported_classes(self):
        return self.element_classes.get_supported_classes()

def new_INP(inp_path):
    return INP(inp_path, new=True)
