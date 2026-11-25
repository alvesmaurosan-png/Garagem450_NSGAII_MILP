"""Verificação de integridade de arquivos e resultados existentes; não chama solver."""
from pathlib import Path
import hashlib,json,csv
r=Path(__file__).resolve().parent
for line in (r/'MANIFEST_SHA256.txt').read_text().splitlines():
    h,p=line.split('  ',1)
    assert hashlib.sha256((r/p).read_bytes()).hexdigest()==h,p
j=json.loads((r/'resultados/NSGAII_FINAL_REV04_20261125_010610/validacao.json').read_text())
assert {x['id'] for x in j if x.get('valid_incumbent')}=={0,1,2,3,4,7}
assert all(len(x['windows'])==121 for x in j if x.get('valid_incumbent'))
print('PASS: integridade e registros anuais preservados; nenhum solver executado.')
