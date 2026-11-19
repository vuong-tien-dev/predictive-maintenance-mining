"""CLI kiểm chứng độc lập; nhận root/gói CSV, không fit hoặc tối ưu mô hình."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from maintenance.review import audit_package, build_review_figures

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--handoff-dir',type=Path)
    parser.add_argument('--output-dir',type=Path)
    args=parser.parse_args()
    report=audit_package(args.root,args.handoff_dir,args.output_dir)
    report['figures']=build_review_figures(args.root,args.output_dir)
    print(json.dumps(report,ensure_ascii=False,indent=2))
