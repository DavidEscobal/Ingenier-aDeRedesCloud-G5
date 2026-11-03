"""Convierte el Markdown de los documentos del proyecto (títulos, párrafos, citas, tablas, código)
a .docx usando solo la biblioteca estándar. Uso: python tools/md2docx.py entrada.md salida.docx
"""
import re
import sys
import zipfile
from xml.sax.saxutils import escape

TEXT_WIDTH = 9638  # A4 con márgenes de 2 cm, en DXA


def runs(text, base=''):
    out = []
    for part in re.split(r'(\*\*[^*]+\*\*|`[^`]+`)', text):
        if not part:
            continue
        props = base
        if part.startswith('**') and part.endswith('**'):
            part, props = part[2:-2], props + '<w:b/>'
        elif part.startswith('`') and part.endswith('`'):
            part, props = part[1:-1], props + '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/>'
        rpr = '<w:rPr>%s</w:rPr>' % props if props else ''
        out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, escape(part)))
    return ''.join(out)


def paragraph(text, style=None, run_props='', keep_next=False):
    ppr = ''
    if style or keep_next:
        ppr = '<w:pPr>%s%s</w:pPr>' % ('<w:pStyle w:val="%s"/>' % style if style else '', '<w:keepNext/>' if keep_next else '')
    return '<w:p>%s%s</w:p>' % (ppr, runs(text, run_props))


def table(rows):
    header, body = rows[0], rows[1:]
    ncols = len(header)
    if ncols == 2 and header[0].strip() == 'Campo':
        widths = [2300, TEXT_WIDTH - 2300]
    else:
        first = min(3600, TEXT_WIDTH // 2) if ncols > 2 else TEXT_WIDTH // ncols
        rest = (TEXT_WIDTH - first) // (ncols - 1) if ncols > 1 else 0
        widths = [first] + [rest] * (ncols - 1)
        widths[-1] += TEXT_WIDTH - sum(widths)
    grid = ''.join('<w:gridCol w:w="%d"/>' % w for w in widths)
    xml = ['<w:tbl><w:tblPr><w:tblW w:w="%d" w:type="dxa"/><w:tblBorders>' % TEXT_WIDTH +
           ''.join('<w:%s w:val="single" w:sz="4" w:space="0" w:color="999999"/>' % b
                   for b in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')) +
           '</w:tblBorders><w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="80" w:type="dxa"/>'
           '<w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>%s</w:tblGrid>' % grid]
    for i, row in enumerate([header] + body):
        cells = []
        for j, cell in enumerate(row):
            shade = '<w:shd w:val="clear" w:color="auto" w:fill="D9E2F3"/>' if i == 0 or (ncols == 2 and j == 0 and header[0].strip() == 'Campo') else ''
            bold = '<w:b/>' if i == 0 else ''
            cells.append('<w:tc><w:tcPr><w:tcW w:w="%d" w:type="dxa"/>%s</w:tcPr>%s</w:tc>'
                         % (widths[j], shade, paragraph(cell.strip(), 'TableText', bold)))
        trpr = '<w:trPr><w:cantSplit/>%s</w:trPr>' % ('<w:tblHeader/>' if i == 0 else '')
        xml.append('<w:tr>%s%s</w:tr>' % (trpr, ''.join(cells)))
    xml.append('</w:tbl>')
    return ''.join(xml) + paragraph('')


def convert(markdown):
    body, lines, i = [], markdown.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('```'):
            i += 1
            while i < len(lines) and not lines[i].startswith('```'):
                body.append(paragraph(lines[i], 'Code'))
                i += 1
        elif line.startswith('|'):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                cells = [c for c in re.split(r'(?<!\\)\|', lines[i].strip())[1:-1]]
                if not all(re.fullmatch(r'\s*:?-{3,}:?\s*', c) for c in cells):
                    rows.append(cells)
                i += 1
            body.append(table(rows))
            continue
        elif line.startswith('### '):
            body.append(paragraph(line[4:], 'Heading2'))
        elif line.startswith('## '):
            body.append(paragraph(line[3:], 'Heading1'))
        elif line.startswith('# '):
            body.append(paragraph(line[2:], 'Title'))
        elif line.startswith('> '):
            body.append(paragraph(line[2:], 'Quote'))
        elif line.strip() and line.strip() != '---':
            body.append(paragraph(line))
        i += 1
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>%s'
            '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1134" w:right="1134" w:bottom="1134" '
            'w:left="1134" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr></w:body></w:document>' % ''.join(body))


STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/><w:sz w:val="21"/><w:lang w:val="es-PE"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="80" w:line="259" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="0" w:after="200"/></w:pPr><w:rPr><w:b/><w:color w:val="1F3864"/><w:sz w:val="36"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="320" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="1F3864"/><w:sz w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:pPr><w:keepNext/><w:spacing w:before="220" w:after="80"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:color w:val="2F5496"/><w:sz w:val="23"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="284"/><w:spacing w:after="40"/></w:pPr><w:rPr><w:i/><w:color w:val="404040"/><w:sz w:val="19"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TableText"><w:name w:val="Table Text"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="20" w:after="20" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="18"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Code"><w:name w:val="Code"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/></w:pPr><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="17"/></w:rPr></w:style>
</w:styles>'''

PARTS = {
    '[Content_Types].xml': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>',
    '_rels/.rels': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
    'word/_rels/document.xml.rels': '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
    'word/styles.xml': STYLES,
}

if __name__ == '__main__':
    source, target = sys.argv[1], sys.argv[2]
    with open(source, encoding='utf-8') as f:
        document = convert(f.read())
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in PARTS.items():
            z.writestr(name, data)
        z.writestr('word/document.xml', document)
    print('Generado ' + target)
