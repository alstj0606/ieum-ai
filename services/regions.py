"""Versioned national administrative names, separate from programme availability.

Legal-dong input is kept verbatim: never equate administrative and legal codes.
"""
from functools import lru_cache
import json
from pathlib import Path
import re

PATH=Path(__file__).resolve().parents[1]/'data/regions.json'

@lru_cache(maxsize=1)
def data():
    payload=json.loads(PATH.read_text());rows=payload['regions']
    if payload['metadata']['kind']!='administrative' or len(rows)<3000:raise ValueError('invalid regional data')
    if len({r[2] for r in rows})!=payload['metadata']['province_count'] or len({r[0] for r in rows})!=len(rows):raise ValueError('invalid national hierarchy')
    for row in rows:
        if len(row)!=5 or not re.fullmatch(r'\d{10}',row[0]) or not re.fullmatch(r'\d{8}',row[1]) or not all(isinstance(v,str) and v for v in row[2:]):raise ValueError('invalid region row')
    return payload

def provinces():return sorted({r[2] for r in data()['regions']})
def districts(province):return sorted({r[3] for r in data()['regions'] if r[2]==province})
def neighbourhoods(province,district):return sorted({r[4] for r in data()['regions'] if r[2:4]==[province,district]})
def short(province):
    return province.replace('특별자치도','').replace('특별자치시','').replace('특별시','').replace('광역시','').removesuffix('도')
def label(location):return ' '.join(location.get(k) or '' for k in ('province','district','neighbourhood')).strip()

def selection(province,district,neighbourhood):
    if neighbourhood not in neighbourhoods(province,district):raise ValueError('unknown administrative area')
    row=next(r for r in data()['regions'] if r[2:]==[province,district,neighbourhood])
    return dict(province=province,city=short(province),district=district,neighbourhood=neighbourhood,code=row[0],kind='administrative',snapshot_at=data()['metadata']['snapshot_at'])

def province_aliases():
    result={p:{p,short(p)} for p in provinces()}
    for p,names in result.items():
        for original,abbreviation in (('충청북도','충북'),('충청남도','충남'),('전라남도','전남'),('경상북도','경북'),('경상남도','경남'),('전북특별자치도','전북')):
            if p==original:names.add(abbreviation)
        if p=='전북특별자치도':names.add('전라북도')
    return result

def address_province(address):
    value=(address or '').strip()
    for p,names in province_aliases().items():
        for name in sorted(names,key=len,reverse=True):
            if value.startswith(name) and (name==p or len(value)==len(name) or value[len(name)].isspace()):return p
    return None


def resolve(text,previous=None):
    """Only exact named administrative parents; ambiguous names need confirmation.

    A legal-dong literal in a stated city/district is searchable without assigning
    it an administrative code. Bare normalized stems never assign a legal code.
    """
    compact=re.sub(r'\s+','',text);previous=previous or {};rows=data()['regions']
    aliases=province_aliases()
    province=next((p for p,names in aliases.items() if any(re.search(r'(?:^|\s)'+re.escape(n)+r'(?:에|에서|\s|$)',text) or n in compact and len(n)>2 for n in names)),None)
    if not province:
        province=next((p for p in provinces() if short(p) in compact and any(r[2]==p and r[3].replace(' ','') in compact for r in rows)),None)
    if province and province not in compact and any(r[2]!=province and r[3].startswith(short(province)+'시') for r in rows):
        return dict(city=None,district=None,neighbourhood=None,ambiguous=True,question=short(province)+'은 어느 시·도에 있는 곳인가요?')
    candidates=[r for r in rows if not province or r[2]==province]
    named=[]
    for p,d in sorted({(r[2],r[3]) for r in candidates}):
        tokens=d.split();hits=[t for t in tokens if t in compact or province and len(t)>2 and t[:-1] not in {'수영','운동','문화','중동'} and t[:-1] in compact]
        if hits and (len(tokens)==1 or len(hits)==len(tokens)):named.append((p,d))
    parents=set(named)
    dong_match=re.search(r'(?:^|\s)([가-힣]{1,12}\d{0,2}(?:동|읍|면))(?:에|이|에서|근처|요|\s|$)',text)
    dong=dong_match.group(1) if dong_match and dong_match.group(1) not in {'운동','활동','이동','처음','화면'} else None
    if not parents and previous.get('province') and not province:
        if previous.get('district'):parents={(previous['province'],previous['district'])}
        else:return dict(previous,neighbourhood=dong or previous.get('neighbourhood'))
    if len(parents)==1:
        p,d=next(iter(parents));neighbour=dong
        last_parent=d.split()[-1]
        if last_parent in text:
            tail=text.rsplit(last_parent,1)[1].lstrip()
            match=re.match(r'([가-힣]{1,12}\d{0,2}(?:동|읍|면))(?:에|이|에서|근처|요|\s|$)',tail)
            if match and match.group(1) not in {'운동','활동','이동'}:neighbour=match.group(1)
        if not neighbour and previous.get('province')==p and previous.get('district')==d:neighbour=previous.get('neighbourhood')
        exact=next((r for r in rows if r[2:]==[p,d,neighbour]),None)
        return dict(province=p,city=short(p),district=d,neighbourhood=neighbour,code=exact[0] if exact and not dong and previous.get('kind')=='administrative' else None,kind='administrative' if exact and not dong and previous.get('kind')=='administrative' else 'user_text')
    if len(parents)>1:
        return dict(city=None,district=None,neighbourhood=None,ambiguous=True,question='같은 이름의 지역이 있어요. 어느 시·도에 있는 곳인가요?')
    if dong and not parents:
        matches=[r for r in candidates if r[4]==dong]
        # Administrative aliases (화곡동/우동) are NOT a legal↔administrative mapping.
        parent_matches={(r[2],r[3]) for r in matches}
        if len(parent_matches)==1:
            p,d=next(iter(parent_matches));return dict(province=p,city=short(p),district=d,neighbourhood=dong,code=None,kind='user_text')
    if province and not named:return dict(province=province,city=short(province),district=None,neighbourhood=dong,code=None,kind='user_text')
    # Unknown city+dong is left to the explicit-text parser; never force it into inventory coverage.
    return None
