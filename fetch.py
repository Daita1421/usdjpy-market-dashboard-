import json,datetime,csv,io,urllib.request,urllib.parse,pathlib
ROOT=pathlib.Path(__file__).parent
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
OUT={'fetched_at':NOW,'items':{}}
HEAD={'User-Agent':'Mozilla/5.0 (compatible; PersonalMarketDashboard/1.0)'}
def get(url):
 req=urllib.request.Request(url,headers=HEAD)
 with urllib.request.urlopen(req,timeout=20) as r:return r.read()
def put(key,points,source,url,unit,frequency):
 pts=[{'t':str(t),'v':round(float(v),5)} for t,v in points if v is not None]
 if pts:OUT['items'][key]={'value':pts[-1]['v'],'previous':pts[-2]['v'] if len(pts)>1 else None,'observed_at':pts[-1]['t'],'history':pts[-100:],'source':source,'url':url,'unit':unit,'frequency':frequency}
def fred(key,series):
 url='https://fred.stlouisfed.org/graph/fredgraph.csv?id='+series
 try:
  rows=csv.DictReader(io.StringIO(get(url).decode('utf-8-sig')))
  put(key,[(r.get('observation_date') or r.get('DATE'),r.get(series)) for r in rows if r.get(series) not in ('','.','NaN',None)],'FRED',url,'%', '日次')
 except Exception as e: print(key,type(e).__name__,str(e)[:100])
def yahoo(key,symbol,unit):
 url='https://query1.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(symbol,safe='')+'?range=5d&interval=15m'
 try:
  j=json.loads(get(url));r=j['chart']['result'][0];cl=r['indicators']['quote'][0]['close']; ts=r['timestamp'];
  pts=[(datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat(),v) for t,v in zip(ts,cl) if v is not None]
  put(key,pts,'Yahoo Finance（非公式取得）',url,unit,'15分足（配信遅延あり）')
 except Exception as e: print(key,type(e).__name__,str(e)[:100])
for k,s in [('us2','DGS2'),('us10','DGS10'),('real10','DFII10'),('vix','VIXCLS')]:fred(k,s)
for k,s,u in [('jp2','JP2Y','%'),('jp10','JP10Y','%'),('dxy','DX-Y.NYB','指数'),('wti','CL=F','USD/bbl'),('brent','BZ=F','USD/bbl')]:
 if k.startswith('jp'):continue # Reliable public 15-min Japan government yield source not confirmed
 yahoo(k,s,u)
# Spread derived only from matching observed dates; otherwise no value.
for key,a,b in [('curve','us10','us2'),('spread2','us2','jp2'),('spread10','us10','jp10')]:
 x,y=OUT['items'].get(a),OUT['items'].get(b)
 if x and y and x['observed_at'][:10]==y['observed_at'][:10]:
  put(key,[(x['observed_at'],x['value']-y['value'])],'計算値','', 'ポイント','元データに準拠')
ROOT.joinpath('data','latest.json').write_text(json.dumps(OUT,ensure_ascii=False,indent=2),encoding='utf-8')
print('Fetched',list(OUT['items']))
