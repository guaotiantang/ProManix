import asyncio
import uvicorn
import multiprocessing
import aiomultiprocess
from Configure import *
from fastapi import FastAPI
from contextlib import asynccontextmanager
from Service_ZIPParser import ZIPParserService
from Service_NFSScanner import NDSFileScanService
from fastapi.middleware.cors import CORSMiddleware
from NDSDBApi import nds_service_api, log_router, nds_info_route, nds_file_route, nds_parser_router

# spawn / fork
multiprocessing.set_start_method('spawn', force=True)
aiomultiprocess.set_start_method('spawn')

routers = []
services = []
nfs_parser = ZIPParserService()
nfs_scanner = NDSFileScanService()


async def start_service():
    await nds_service_api.init()
    routers.append(log_router)
    routers.append(nds_info_route)
    routers.append(nds_file_route)
    routers.append(nds_parser_router)
    print("INFO Append routes.")
    for router in routers:
        app.include_router(router)
    print("INFO Routers load success.")
    print("INFO Services starting...")
    services.append(asyncio.create_task(nfs_scanner.run()))
    services.append(asyncio.create_task(nfs_parser.run()))


async def close_service():
    try:
        await nfs_scanner.stop()
        await nfs_parser.stop()
    except Exception:
        pass
    try:
        await asyncio.gather(*services)
    except Exception:
        pass
    print("INFO Services closed.")
    print("INFO Wait database pool close...")
    await nds_service_api.MysqlPool.close_pool()
    print("INFO Database pool closed.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    url = f"http://{ModuleInfo.get('ModuleParams').get('host')}:{ModuleInfo.get('ModuleParams').get('port')}"
    print(f"INFO Services control url: {url}")
    await start_service()
    print("INFO NDSScanner Started.")
    yield
    await close_service()
    print("INFO NDSScanner Stopped.")


app = FastAPI(lifespan=lifespan)

#  跨域访问
# noinspection PyTypeChecker
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/")
async def root():
    return {"message": "Service Running"}


@app.get("/info")
async def info():
    _info = ModuleInfo.copy()
    _info.pop("ModuleParams", None)
    return _info


@app.get("/services/restart")
async def services_restart():
    global services
    print("INFO Services restarting...")
    try:
        await nfs_scanner.stop()
    except Exception:
        pass
    try:
        await nfs_parser.stop()
    except Exception:
        pass
    try:
        await asyncio.gather(*services)
        services = [asyncio.create_task(nfs_scanner.run()), asyncio.create_task(nfs_parser.run())]
        return {"result": "success"}
    except Exception:
        pass
    return {"result": "done"}


if __name__ == "__main__":
    print("INFO Start web service")
    ModuleParams = ModuleInfo.get("ModuleParams")
    config = uvicorn.Config(**ModuleParams)
    server = uvicorn.Server(config)
    server.run()
