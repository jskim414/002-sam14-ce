"""Measure local HTTP API timings; never describe these as Preview/mobile results."""
import argparse
import math
from pathlib import Path
import statistics
import sys
import threading
import time
from urllib.request import urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import write_json,sha256
from web.server import create_server

def measure(database):
    server=create_server('127.0.0.1',0,database)
    server.RequestHandlerClass.log_message=lambda *args:None
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    routes=['officers?scenario=ce-05','officers/147?scenario=ce-05','officers/147/relationships?scenario=ce-05',
            'officers?scenario=ce-05&state=ACTIVE_FORCE&trait=196&policy=47&doctrine=2&level_min=1&sort=intelligence&order=desc']
    output=[]
    try:
        for route in routes:
            samples=[]
            for i in range(101):
                start=time.perf_counter()
                with urlopen(f'http://127.0.0.1:{server.server_port}/api/v1/{route}') as response:
                    response.read()
                    if response.status!=200:raise ValueError('HTTP failure')
                samples.append((time.perf_counter()-start)*1000)
            warm=sorted(samples[1:])
            output.append({'route':route,'warm_samples':100,'first_request_ms':round(samples[0],3),
                           'warm_median_ms':round(statistics.median(warm),3),'warm_p95_ms':round(warm[math.ceil(len(warm)*.95)-1],3),
                           'warm_max_ms':round(max(warm),3)})
        return {'environment':'Windows localhost Python ThreadingHTTPServer; no mobile network, browser rendering or platform cold-start measurement',
                'database_sha256':sha256(database),'database_bytes':database.stat().st_size,'results':output}
    finally:server.shutdown();server.server_close();thread.join()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();r=measure(a.database);write_json(a.report,r)
    for item in r['results']:print(item['route'],'p95',item['warm_p95_ms'],'ms')
