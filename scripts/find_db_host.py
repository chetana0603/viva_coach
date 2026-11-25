"""
Find the Supabase pooler address that accepts your DATABASE_URL credentials.

"tenant/user ... not found" means the pooler host/region does not match the project.
This tries the likely Supabase pooler hosts with the user and password already in
.env and reports which one connects. Passwords are never printed.

    python scripts/find_db_host.py           # test only
    python scripts/find_db_host.py --write   # also fix DATABASE_URL in .env (backup: .env.bak)
"""
import os
import shutil
import sys

import psycopg
from dotenv import dotenv_values
from sqlalchemy.engine import make_url

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = os.path.join(ROOT, ".env")
REGIONS = ["ap-south-1", "ap-southeast-1"]
PREFIXES = ["aws-0", "aws-1"]


def try_connect(url):
    plain = url.set(drivername="postgresql")
    try:
        with psycopg.connect(plain.render_as_string(hide_password=False),
                             connect_timeout=8) as conn:
            n = conn.execute("select count(*) from information_schema.tables "
                             "where table_schema='public'").fetchone()[0]
        return True, f"connected ({n} tables in public schema)"
    except Exception as e:  # noqa: BLE001
        msg = str(e).splitlines()[0]
        if url.password:
            msg = msg.replace(url.password, "****")
        return False, msg[:110]


def main():
    raw = dotenv_values(ENV).get("DATABASE_URL")
    if not raw:
        sys.exit("No DATABASE_URL in .env")
    url = make_url(raw)
    print(f"user={url.username}  current host={url.host}:{url.port}\n")

    winner = None
    for region in REGIONS:
        for prefix in PREFIXES:
            cand = url.set(host=f"{prefix}-{region}.pooler.supabase.com", port=6543)
            ok, msg = try_connect(cand)
            print(f"{'OK  ' if ok else 'fail'}  {cand.host}:6543  {msg}")
            if ok and winner is None:
                winner = cand

    if not winner:
        print("\nNo host accepted these credentials. Either the password was reset "
              "or the project ref differs - copy the string from Supabase > Connect.")
        return
    print(f"\nWorking host: {winner.host}")
    if "--write" in sys.argv:
        shutil.copy(ENV, ENV + ".bak")
        lines = open(ENV, encoding="utf-8").read().splitlines()
        new = winner.render_as_string(hide_password=False)
        lines = [f"DATABASE_URL={new}" if ln.startswith("DATABASE_URL=") else ln
                 for ln in lines]
        open(ENV, "w", encoding="utf-8").write("\n".join(lines) + "\n")
        print("Updated DATABASE_URL in .env (old file saved as .env.bak).")
    else:
        print("Run again with --write to save it to .env.")


if __name__ == "__main__":
    main()
