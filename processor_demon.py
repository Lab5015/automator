import os
import subprocess
import asyncio
from models import SessionLocal, Run
from sqlalchemy import select
import time

MTDDAQ_PATH = "/home/cmsdaq/DAQ/mtd_daq/"

plotters = {
    "tp": "tofhir_tp_plot.py",
    "lyso": "tofhir_lyso_plot.py",
    "disc": "tofhir_disc_scan_plot.py",
    "iv": "tofhir_iv_scan_plot.py",
    "tec": "temps_plot.py",
}


async def process_run(run_id: Run):
    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        if not run:
            print(f"[runner] Run ID {run_id} not found")
            return

        # ➕ Mark as processing
        run.status = "processing"
        await session.commit()  # commit to reflect in DB

    await asyncio.sleep(0.1)

    async with SessionLocal() as session:
        run = await session.get(Run, run_id)
        env = os.environ.copy()
        env["PATH"] = ":".join(
            list(filter(lambda k: ".venv" not in k, env["PATH"].split(":")))
        )
        start = time.time()

        if run.run_type == "lyso" or run.run_type == "tp":
            proc = subprocess.Popen(
                f"which python; cd {MTDDAQ_PATH}; . start.sh; tofhir_reco.py {run.run_number}; {plotters[run.run_type]} {run.run_number}",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                executable="/bin/bash",
                env=env,
            )
        else:
            proc = subprocess.Popen(
                f"which python; cd {MTDDAQ_PATH}; . start.sh; {plotters[run.run_type]} {run.run_number}",
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                executable="/bin/bash",
                env=env,
            )

        stdout, stderr = proc.communicate()
        elapsed = round((time.time() - start) / 60, 2)

        run.status = "failed on runner" if proc.returncode != 0 else "completed"
        run.stdout = (
            f"Done processing in {elapsed} minutes\nOutput:\n" + stdout.decode()
        )
        run.stderr = env["PATH"] + "\n" + stderr.decode()

        link = "#"
        if proc.returncode == 0:
            if run.run_type in ["lyso", "tp"]:
                link = f"http://pc-mtd-tray/tray_qaqc/tofhir/plots_run_{run.run_number}"
            elif run.run_type == "disc":
                link = f"http://pc-mtd-tray/tray_qaqc/disc_scan/run_{run.run_number}"
            elif run.run_type == "iv":
                link = f"http://pc-mtd-tray/tray_qaqc/iv_scan/run_{run.run_number}"
            elif run.run_type == "tec":
                link = f"http://pc-mtd-tray/tray_qaqc/temps/run_{run.run_number}"
        print(link)

        run.plot_link = link

        await session.commit()

    print("done")


async def poll_db():
    while True:
        async with SessionLocal() as session:
            result = await session.execute(
                select(Run).where(Run.status == "queued").order_by(Run.run_number)
            )
            runs = result.scalars().all()

        if runs:
            print(
                f"[{time.strftime('%H:%M:%S')}] Found {len(runs)} run(s) to process..."
            )
            for run in runs:
                await process_run(run.id)
            else:
                print(f"[{time.strftime('%H:%M:%S')}] No queued runs.")

        await asyncio.sleep(2)  # polling interval


if __name__ == "__main__":
    asyncio.run(poll_db())
