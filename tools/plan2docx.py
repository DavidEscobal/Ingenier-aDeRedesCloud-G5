"""Genera el .docx del plan de pruebas con el formato del caso modelo de la guía LAB6 (§3.3, «3.1.2»):
título del caso en la primera fila, etiquetas en negrita, viñetas y pasos numerados.

Uso: python tools/plan2docx.py docs/pruebas/PLAN_PRUEBAS_SLICE_MANAGER.md salida.docx
"""
import re
import sys
import zipfile
from xml.sax.saxutils import escape

sys.path.insert(0, __import__('os').path.dirname(__file__))
import md2docx  # noqa: E402

LABEL_W, TEXT_W = 2500, md2docx.TEXT_WIDTH - 2500
LABELS = [('Número de caso', 'Número de Caso'), ('Tipo de prueba', 'Tipo de prueba'), ('Objetivos', 'Objetivos'),
          ('Prerrequisitos', 'Prerrequisitos'), ('Procedimiento', 'Procedimiento'),
          ('Resultados esperados', 'Resultados Esperados'), ('Resultado obtenido', 'Resultados Obtenidos'),
          ('Evidencias', 'Evidencias'), ('Comentarios', 'Comentarios y/o observaciones')]
BULLET, DECIMAL = 1, 2
SUITE_LOG = 'docs/evidencias/F1/suite_unittest_20261103.txt'


class Numbering:
    """Cada lista numerada usa su propia instancia para reiniciar en 1."""
    def __init__(self):
        self.next_id = 10
        self.instances = []

    def new_decimal(self):
        self.next_id += 1
        self.instances.append(self.next_id)
        return self.next_id

    def xml(self):
        def abstract(aid, fmt, text):
            return ('<w:abstractNum w:abstractNumId="%d"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0">'
                    '<w:start w:val="1"/><w:numFmt w:val="%s"/><w:lvlText w:val="%s"/><w:lvlJc w:val="left"/>'
                    '<w:pPr><w:ind w:left="284" w:hanging="227"/></w:pPr>%s</w:lvl></w:abstractNum>'
                    % (aid, fmt, text, '<w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr>' if fmt == 'bullet' else ''))
        nums = '<w:num w:numId="%d"><w:abstractNumId w:val="0"/></w:num>' % BULLET
        nums += ''.join('<w:num w:numId="%d"><w:abstractNumId w:val="1"/><w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/>'
                        '</w:lvlOverride></w:num>' % n for n in self.instances)
        return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering xmlns:w="http://schemas.openxmlformats.org/'
                'wordprocessingml/2006/main">%s%s%s</w:numbering>' % (abstract(0, 'bullet', ''), abstract(1, 'decimal', '%1.'), nums))


def clean(text):
    return text.replace('`', '').strip()


def para(text, num=None, bold=False, center=False, size=19, keep=True):
    # keepNext en todas las filas menos la última: Word no parte el caso entre páginas.
    ppr = ('<w:keepNext/>' if keep else '') + '<w:spacing w:before="20" w:after="20" w:line="240" w:lineRule="auto"/>'
    if num:
        ppr += '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="%d"/></w:numPr>' % num
    if center:
        ppr += '<w:jc w:val="center"/>'
    base = '<w:sz w:val="%d"/>' % size + ('<w:b/>' if bold else '')
    return '<w:p><w:pPr>%s</w:pPr>%s</w:p>' % (ppr, md2docx.runs(clean(text), base))


def split_items(text, sep='; '):
    items = [x.strip().rstrip('.') + '.' for x in clean(text).split(sep) if x.strip()]
    return [x[0].upper() + x[1:] for x in items]


def steps(text):
    parts = [p.strip() for p in re.split(r'(?:^|\s)\d+\)\s', clean(text)) if p.strip()]
    return parts or [clean(text)]


def result_text(text):
    text = clean(text)
    kind = 'PASS [REAL]' if 'PASS [REAL]' in text else 'PASS [AUT]' if 'PASS [AUT]' in text else 'NT' if 'NT' in text else None
    rest = re.sub(r'^\*\*(PASS \[(REAL|AUT)\]|NT)\*\*\s*(—\s*)?', '', text, count=1)
    rest = re.sub(r'\*\*PASS \[(REAL|AUT)\]\*\*', lambda m: 'PASS (%s)' % ('clúster real' if m.group(1) == 'REAL' else 'automática'), rest)
    rest = rest.replace(' · ', '; ').strip()
    label = {'PASS [REAL]': '**PASS** — ejecutado en el clúster OpenStack real.',
             'PASS [AUT]': '**PASS** — prueba automática (backend simulado, sin infraestructura real).',
             'NT': '**NT** — no realizado: los requisitos aún no se cumplen.'}.get(kind, text)
    rest = re.sub(r'\*\*', '', rest)
    items = [label] + ([rest[0].upper() + rest[1:]] if rest and rest != 'función pendiente de implementación.' else [])
    return items


def evidence_items(text):
    text = clean(text)
    if text in ('—', '-', ''):
        return ['Pendiente (se generará al ejecutar la prueba).']
    tests = re.findall(r'test_[a-z0-9_]+', text)
    items = []
    if tests:
        items.append('Registro de la suite automática: %s.' % SUITE_LOG)
        items.append('Pruebas ejecutadas: ' + ', '.join(tests) + '.')
    rest = re.sub(r'test_[a-z0-9_]+(,\s*)?', '', text).replace('(log de la suite)', '').strip(' ;,.')
    for part in [p.strip(' ,.') for p in re.split(r';\s*', rest) if p.strip(' ,.')]:
        items.append((part if part.startswith('docs/') else part[0].upper() + part[1:]) + '.')
    return items


def case_table(num_id, title, fields, numbering):
    widths = [LABEL_W, TEXT_W]
    border = ''.join('<w:%s w:val="single" w:sz="6" w:space="0" w:color="000000"/>' % b
                     for b in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
    rows = ['<w:tr><w:trPr><w:cantSplit/></w:trPr><w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/><w:gridSpan w:val="2"/>'
            '<w:shd w:val="clear" w:color="auto" w:fill="D9D9D9"/><w:vAlign w:val="center"/></w:tcPr>%s</w:tc></w:tr>'
            % (md2docx.TEXT_WIDTH, para('%s %s' % (num_id, title), bold=True, center=True, size=22))]
    for key, label in LABELS:
        value = fields.get(key, '—')
        if key == 'Prerrequisitos':
            content = ''.join(para(x, BULLET) for x in split_items(value))
        elif key == 'Procedimiento':
            n = numbering.new_decimal()
            content = ''.join(para(x, n) for x in steps(value))
        elif key == 'Resultados esperados':
            content = ''.join(para(x, BULLET) for x in split_items(value))
        elif key == 'Resultado obtenido':
            content = ''.join(para(x, BULLET) for x in result_text(value))
        elif key == 'Evidencias':
            content = ''.join(para(x, BULLET) for x in evidence_items(value))
        elif key == 'Comentarios':
            n = numbering.new_decimal()
            content = ''.join(para(x, n) for x in split_items(value, '; ')) if clean(value) not in ('—', '') else para('—')
        else:
            content = para(value)
        if key == 'Comentarios':
            content = content.replace('<w:keepNext/>', '')
        rows.append('<w:tr><w:trPr><w:cantSplit/></w:trPr><w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/><w:vAlign w:val="center"/>'
                    '</w:tcPr>%s</w:tc><w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/></w:tcPr>%s</w:tc></w:tr>'
                    % (LABEL_W, para(label, bold=True), TEXT_W, content))
    return ('<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/><w:tblBorders>%s</w:tblBorders><w:tblLayout w:type="fixed"/>'
            '<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="100" w:type="dxa"/><w:bottom w:w="40" w:type="dxa"/>'
            '<w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>%s</w:tblGrid>%s</w:tbl>'
            % (md2docx.TEXT_WIDTH, border, ''.join('<w:gridCol w:w="%d"/>' % w for w in widths), ''.join(rows))
            + '<w:p><w:pPr><w:spacing w:after="160"/></w:pPr></w:p>')


def build(markdown):
    numbering = Numbering()
    first_case = markdown.index('\n## 1.1 ')
    intro = re.sub(r'`([^`]*)`', r'\1', markdown[:first_case])
    body = [md2docx.convert(intro).split('<w:body>')[1].split('<w:sectPr>')[0]]
    blocks = re.split(r'(?m)^(## .*|### .*)$', markdown[first_case:])
    i = 1
    while i < len(blocks):
        header, content = blocks[i], blocks[i + 1]
        if header.startswith('### '):
            num_id, title = header[4:].split(' ', 1)
            fields = {}
            for line in content.splitlines():
                m = re.match(r'\|\s*([^|]+?)\s*\|\s*(.*)\s*\|\s*$', line)
                if m and m.group(1) not in ('Campo', '---'):
                    fields[m.group(1)] = m.group(2)
            body.append(case_table(num_id, title, fields, numbering))
        else:
            title = header[3:]
            if title.startswith('1.'):
                body.append(md2docx.paragraph(title, 'Heading1'))
            else:  # Trazabilidad, Cómo reproducir: Markdown normal
                body.append(md2docx.convert(re.sub(r'`([^`]*)`', r'\1', header + content)).split('<w:body>')[1].split('<w:sectPr>')[0])
                i += 2
                continue
        i += 2
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
                'wordprocessingml/2006/main"><w:body>%s<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" '
                'w:right="1134" w:bottom="1134" w:left="1134" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr>'
                '</w:body></w:document>' % ''.join(body))
    return document, numbering.xml()


if __name__ == '__main__':
    source, target = sys.argv[1], sys.argv[2]
    with open(source, encoding='utf-8') as f:
        document, numbering = build(f.read())
    parts = dict(md2docx.PARTS)
    parts['[Content_Types].xml'] = parts['[Content_Types].xml'].replace(
        '</Types>', '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.'
        'wordprocessingml.numbering+xml"/></Types>')
    parts['word/_rels/document.xml.rels'] = parts['word/_rels/document.xml.rels'].replace(
        '</Relationships>', '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
        'numbering" Target="numbering.xml"/></Relationships>')
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data)
        z.writestr('word/document.xml', document)
        z.writestr('word/numbering.xml', numbering)
    print('Generado ' + target)
