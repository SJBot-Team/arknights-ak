# -*- coding: utf-8 -*-
"""Extract dataValidation prompts / allowed lists from an xlsm sheet as UTF-8."""
import zipfile, re, io, html, sys

z = zipfile.ZipFile(sys.argv[1])
x = z.read(sys.argv[2]).decode('utf-8')
m = re.search(r'<dataValidations.*?</dataValidations>', x, re.S)
out = io.open(sys.argv[3], 'w', encoding='utf-8')
if not m:
    print('no dataValidations', file=out)
else:
    for dv in re.findall(r'<dataValidation .*?(?:/>|</dataValidation>)', m.group(0), re.S):
        sq = re.search(r'sqref="([^"]*)"', dv)
        pr = re.search(r'prompt="([^"]*)"', dv)
        ty = re.search(r'type="(\w+)"', dv)
        f1 = re.search(r'<formula1>(.*?)</formula1>', dv, re.S)
        f2 = re.search(r'<formula2>(.*?)</formula2>', dv, re.S)
        print('sqref=%-14s type=%-8s f1=%-24s f2=%-6s prompt=%s' % (
            sq.group(1) if sq else '', ty.group(1) if ty else '',
            f1.group(1) if f1 else '', f2.group(1) if f2 else '',
            html.unescape(pr.group(1)).replace('\n', ' / ') if pr else ''), file=out)
out.close()
print('written', sys.argv[3])
