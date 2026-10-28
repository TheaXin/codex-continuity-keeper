#!/usr/bin/env python3
"""Repeatable interruption/export/resume demo using isolated installed code."""
import argparse,json
from acceptance import run_acceptance,save_report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',help='NEW directory OUTSIDE the source checkout; omit for automatic cleanup');p.add_argument('--report');a=p.parse_args()
    result=run_acceptance(workspace=a.workspace)
    if a.report:save_report(a.report,result)
    for step in result['steps']:print('PASS '+step['name']+': '+step['evidence'])
    print(json.dumps(result,ensure_ascii=False,indent=2))
