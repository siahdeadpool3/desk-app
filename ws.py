import asyncio,websockets,json
async def m():
  async with websockets.connect("wss://pumpportal.fun/api/data") as w:
    await w.send(json.dumps({"method":"subscribeMigration"}))
    while True:
      x=await asyncio.wait_for(w.recv(),600); print(x,flush=True)
      d=json.loads(x)
      if "mint" in d: open("logs/raw/pumpportal_migration.json","w").write(x); return
asyncio.run(m())
