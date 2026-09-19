"""Restore a verified CE package into a new local directory, without replacing a service."""
import argparse
import shutil
from pathlib import Path
from common import ROOT,output_path
from check_package import verify

def restore(source,destination):
    source=source.resolve(strict=True);destination=output_path(destination)
    boundary=(ROOT/'.artifacts/packages').resolve()
    if not source.is_relative_to(boundary) or not destination.is_relative_to(boundary):raise ValueError('Restore must stay inside CE package storage')
    verify(source)
    shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__','.vercel'))
    verify(destination)
    return destination

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(restore(a.source,a.output))
