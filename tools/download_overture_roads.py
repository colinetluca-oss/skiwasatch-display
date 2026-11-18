exec(open('ov.py').read().split("keys=open")[0])
import json, pyarrow.compute as pc
hits=json.load(open('ov_hits.json'))
k,rgs=hits[0]; pf=pq.ParquetFile(fopen(base+k))
print(pf.schema_arrow.names)
cols=['id','geometry','bbox','class','names','subtype','connectors','road_flags']
cols=[c for c in cols if c in pf.schema_arrow.names]
from concurrent.futures import ThreadPoolExecutor
def rd(i): return pq.ParquetFile(fopen(base+k)).read_row_group(i,columns=cols)
with ThreadPoolExecutor(8) as ex: tabs=list(ex.map(rd,rgs))
t=pa.concat_tables(tabs)
b=t.column('bbox').combine_chunks()
xmin=pc.struct_field(b,'xmin');xmax=pc.struct_field(b,'xmax');ymin=pc.struct_field(b,'ymin');ymax=pc.struct_field(b,'ymax')
m=pc.and_(pc.and_(pc.less_equal(xmin,BB[2]),pc.greater_equal(xmax,BB[0])),pc.and_(pc.less_equal(ymin,BB[3]),pc.greater_equal(ymax,BB[1])))
t=t.filter(m)
cl=t.column('class').to_pylist()
from collections import Counter; print(len(cl), Counter(cl).most_common(12))
keep=[i for i,c in enumerate(cl) if c in ('motorway','trunk','primary','secondary','tertiary','motorway_link','trunk_link','primary_link','residential','unclassified','living_street','service')]
t=t.take(keep)
pq.write_table(t,'roads_raw.parquet'); print(t.num_rows)
