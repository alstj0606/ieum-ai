"""Build name/code-only picker data from the attributed SGIS-derived GeoJSON.

Run on an explicitly downloaded, reviewed snapshot; no runtime network dependency.
"""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re

SOURCE='https://sgis.kostat.go.kr/view/pss/downloadList'
MIRROR='https://github.com/vuski/admdongkor'
COMMIT='078ef4ac13b8bfeb215d2eabace49f4fdea71d5e'


def build(raw, snapshot, source_commit=COMMIT):
    date.fromisoformat(snapshot)
    if not re.fullmatch(r"[0-9a-f]{40}",source_commit):raise ValueError("pin a source commit")
    source=json.loads(raw)
    if source.get('name')!='HangJeongDong_ver'+snapshot.replace('-',''):raise ValueError('snapshot label does not match input')
    features=source['features'];rows=[]
    for feature in features:
        p=feature['properties'];province=p['sidonm'];district=re.sub(r'(시)(?=[가-힣]+구$)',r'\1 ',p['sggnm'])
        name=p['adm_nm'].split()[-1]
        rows.append([p['adm_cd2'],p['adm_cd'],province,district,name])
    rows.sort()
    if not 15<=len({r[2] for r in rows})<=20 or len(rows)<3000 or len({r[0] for r in rows})!=len(rows):raise ValueError('incomplete national snapshot')
    return {'metadata':{'schema_version':1,'province_count':len({r[2] for r in rows}),'kind':'administrative','snapshot_at':snapshot,'retrieved_at':date.today().isoformat(),
        'official_origin':SOURCE,'distribution':MIRROR,'distribution_commit':source_commit,
        'download_url':f'https://raw.githubusercontent.com/vuski/admdongkor/{source_commit}/ver{snapshot.replace("-","")}/HangJeongDong_ver{snapshot.replace("-","")}.geojson',
        'input_sha256':hashlib.sha256(raw).hexdigest(),'license':'SGIS KOGL Type 1; vuski/admdongkor CC BY 4.0',
        'attribution':'통계청 SGIS 공공누리 제1유형 행정동 경계 가공: vuski/admdongkor (CC BY 4.0). 이음 AI는 이름·코드만 추출.',
        'verification':'공식 원본 다운로드는 환경에서 차단됨. 출처·가공본과 기준일 확인. 이후 개편·법정동 대응은 미검증.',
        'columns':['mois_code','statistics_code','province','district','neighbourhood']},'regions':rows}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('--snapshot',required=True);parser.add_argument('--source-commit',default=COMMIT);parser.add_argument('--output',default='data/regions.json')
    args=parser.parse_args();out=build(Path(args.input).read_bytes(),args.snapshot,args.source_commit)
    metadata=json.dumps(out['metadata'],ensure_ascii=False,indent=2)
    records=',\n'.join('    '+json.dumps(row,ensure_ascii=False,separators=(',',':')) for row in out['regions'])
    Path(args.output).write_text('{\n  "metadata": '+metadata+',\n  "regions": [\n'+records+'\n  ]\n}\n')
    print(f"{len(out['regions'])} administrative areas")
