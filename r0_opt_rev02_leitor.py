"""R0-OPT-REV02: leitura independente do certificado; nunca executa MILP."""
import argparse
import json
from pathlib import Path
from math import isfinite

EXPECTED = 'ANNUAL_ENCODED_ELECTRICAL_INTEGER_FEASIBLE_FIXED_SELECTION'

def inspect_certificate(path):
    data=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    errors=[]
    if data.get('status')!=EXPECTED: errors.append('status da certificacao divergente')
    if data.get('annual_integer_feasibility_certified') is not True: errors.append('factibilidade inteira nao certificada')
    if data.get('n_bev')!=100: errors.append('incumbente nao e de 100 BEV')
    if len(data.get('selected_vehicle_ids',[]))!=100: errors.append('selecao de veiculos incompleta')
    days=data.get('days',[])
    if len(days)!=365: errors.append('nao ha 365 dias')
    peaks=[]
    for i,day in enumerate(days):
        if day.get('day')!=i or day.get('status')!='MILP_INTEGER_FEASIBLE' or day.get('milp_status')!=0:
            errors.append(f'dia {i}: registro nao certificado')
        peak=day.get('pcc_peak_kw')
        if not isinstance(peak,(int,float)) or isinstance(peak,bool) or not isfinite(peak) or peak<0:
            errors.append(f'dia {i}: pico invalido')
        else: peaks.append(peak)
        if abs(day.get('soc_start_kwh',float('nan'))-day.get('soc_end_kwh',float('nan')))>1e-5:
            errors.append(f'dia {i}: borda SOC divergente')
    f2=max(peaks) if len(peaks)==365 and not errors else None
    if f2 is not None and f2>2500+1e-5: errors.append('limite PCC violado');f2=None
    return {'revision':'R0-OPT-REV02','source':str(path),'n_bev':data.get('n_bev'),
            'days_checked':len(days),'F2_peak_from_daily_records_kw':f2,
            'F2_full_15min_series_verified':False,
            'grid_energy_kwh':None,'annual_grid_bill_brl':None,
            'F1_brl_per_pkm':None,'F1_status':'BLOCKED_MISSING_COST_AND_SERVICE_RECONCILIATION',
            'status':'READ_ONLY_CERTIFICATE_CONSISTENT' if not errors else 'CERTIFICATE_DATA_INCONSISTENT',
            'errors':errors,'notes':['Picos diarios permitem maximo anual, nao faturamento por posto horario.',
             'NPZ diarios e tarifas reconciliadas sao necessarios para faturamento R0.',
             'Nenhum solver ou rotina de certificacao e executado.']}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('certificate',help='Caminho para resultado_cert_r0_n100.json')
    ap.add_argument('--output',default='resultados/R0_OPT_REV02/diagnostico_leitura.json')
    args=ap.parse_args()
    result=inspect_certificate(args.certificate)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='notes'},ensure_ascii=False,indent=2))
    if result['errors']:raise SystemExit(2)
if __name__=='__main__':main()
