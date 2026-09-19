"""Reproduce extraction metrics, without hiding unsupported or failed documents."""
import json
import platform
import sys
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.extraction import FIELDS, extract_pdf, validate

ROOT = Path(__file__).resolve().parents[1]


def evaluate(group):
    folder=ROOT/'fixtures'/group
    labels=json.loads((folder/'labels.json').read_text(encoding='utf-8'))
    cases=labels if isinstance(labels,list) else labels['cases']
    if group=='unseen':
        cases=[{'file':c['file'],'fields':c['expected'],
                'expected_issues':[] if c['case']=='valid' else [c['case']]} for c in cases]
    details=[]
    totals=dict(documents=len(cases),text_documents=0,present_fields=0,correct_present_fields=0,
                null_fields=0,correct_null_fields=0,all_seven_slots_correct=0,
                complete_documents=0,complete_documents_all_fields_correct=0,
                checks_passed=0,checks_blocked=0,source_valid_passed=0,source_valid_blocked=0,
                source_invalid_passed=0,source_invalid_blocked=0,scans_blocked=0)
    started=perf_counter()
    for case in cases:
        result=extract_pdf((folder/case['file']).read_bytes())
        issues=validate(result['fields'])
        codes={i['code'] for i in issues}
        if result['document_issues']:codes.add('document')
        if result['ambiguous']:codes.add('ambiguous')
        scan=case.get('scan',False)
        diff=[]
        if scan:
            totals['scans_blocked']+=int('document' in codes)
        else:
            totals['text_documents']+=1
            for f in FIELDS:
                expected=case['fields'][f]
                bucket='null' if expected is None else 'present'
                totals[bucket+'_fields']+=1
                if result['fields'][f]==expected:
                    totals['correct_'+bucket+'_fields']+=1
                else:diff.append({'field':f,'expected':expected,'actual':result['fields'][f]})
            totals['all_seven_slots_correct']+=int(not diff)
            if all(v is not None for v in case['fields'].values()):
                totals['complete_documents']+=1
                totals['complete_documents_all_fields_correct']+=int(not diff)
            totals['checks_blocked' if codes else 'checks_passed']+=1
            quality='source_invalid' if case['expected_issues'] else 'source_valid'
            totals[quality+('_blocked' if codes else '_passed')]+=1
        details.append({'file':case['file'],'scan':scan,'expected_issues':case['expected_issues'],
                        'actual_issue_codes':sorted(codes),'fields':result['fields'],'mismatches':diff})
    totals['elapsed_seconds']=round(perf_counter()-started,3)
    return {'summary':totals,'documents':details}


if __name__=='__main__':
    result={'environment':{'python':platform.python_version(),'system':platform.system()},
            'method':'Exact normalized field equality; null slots separate; one scan excluded from text extraction denominator and reported separately. No human corrections before scoring. All uploaded documents require human review (100%).',
            'development':evaluate('development'),'regression':evaluate('regression')}
    if (ROOT/'fixtures'/'unseen'/'labels.json').exists():
        result['unseen']=evaluate('unseen')
    (ROOT/'docs'/'evaluation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({g:result[g]['summary'] for g in ('development','regression','unseen') if g in result},indent=2))
