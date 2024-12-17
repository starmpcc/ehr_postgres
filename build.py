import argparse
import os
import subprocess
import sys

start = """FROM postgres:17.2
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgres
RUN apt update && apt install git make -y
RUN mkdir /data

USER postgres

RUN cd ~
"""

mimic_iv = """#!/bin/bash
set -e
echo "START BUILDING MIMIC-IV"

git clone https://github.com/MIT-LCP/mimic-code.git /tmp/mimic-code
cd /tmp/mimic-code
if ! psql -U postgres -lqt | cut -d \| -f 1 | grep -wq mimiciv; then
    createdb mimiciv
fi
psql -d mimiciv -f mimic-iv/buildmimic/postgres/create.sql
psql -d mimiciv -v ON_ERROR_STOP=1 -v mimic_data_dir=/tmp/mimic_iv -f mimic-iv/buildmimic/postgres/load{}.sql
psql -d mimiciv -v ON_ERROR_STOP=1 -v mimic_data_dir=/tmp/mimic_iv -f mimic-iv/buildmimic/postgres/constraint.sql
psql -d mimiciv -v ON_ERROR_STOP=1 -v mimic_data_dir=/tmp/mimic_iv -f mimic-iv/buildmimic/postgres/index.sql
psql -d mimiciv -v ON_ERROR_STOP=1 -f mimic-iv/buildmimic/postgres/validate.sql
cd mimic-iv/concepts_postgres
psql -d mimiciv -v ON_ERROR_STOP=1 -f postgres-make-concepts.sql

cd ~
rm -rf /tmp/mimic-code

echo "FINISH BUILDING MIMIC-IV"
"""

mimic_iv_ed = """#!/bin/bash
set -e
echo "START BUILDING MIMIC-IV-ED"

git clone https://github.com/MIT-LCP/mimic-code.git /tmp/mimic-code
cd /tmp/mimic-code
if ! psql -U postgres -lqt | cut -d \| -f 1 | grep -wq mimiciv; then
    createdb mimiciv
fi
psql -d mimiciv -f mimic-iv-ed/buildmimic/postgres/create.sql
psql -d mimiciv -v ON_ERROR_STOP=1 -v mimic_data_dir=/tmp/mimic_iv_ed -f mimic-iv-ed/buildmimic/postgres/load_gz.sql
psql -d mimiciv -v ON_ERROR_STOP=1 -v mimic_data_dir=/tmp/mimic_iv_ed -f mimic-iv-ed/buildmimic/postgres/validate.sql

cd ~
rm -rf /tmp/mimic-code

echo "FINISH BUILDING MIMIC-IV-ED"
"""

mimic_iii = """#!/bin/bash
set -e
echo "START BUILDING MIMIC-III"

git clone https://github.com/MIT-LCP/mimic-code.git /tmp/mimic-code
cd /tmp/mimic-code/mimic-iii/buildmimic/postgres
createdb mimiciii
make mimic{} datadir="/tmp/mimic_iii" DBNAME="mimiciii"
cd ../../concepts_postgres
psql -d mimiciii -c "SET search_path TO mimiciii;" -f postgres-functions.sql -f postgres-make-concepts.sql

cd ~
rm -rf /tmp/mimic-code

echo "FINISH BUILDING MIMIC-III"
"""


eicu = """
#!/bin/bash
set -e
echo "START BUILDING eICU"

git clone https://github.com/mit-lcp/eicu-code.git /tmp/eicu-code
cd /tmp/eicu-code/build-db/postgres
make initialize
make eicu{} datadir="/tmp/eicu/"

cd ~
rm -rf /tmp/eicu-code

echo "FINISH BUILDING eICU"
"""

script_dict = {
    "mimic_iv": mimic_iv,
    "mimic_iv_ed": mimic_iv_ed,
    "mimic_iii": mimic_iii,
    "eicu": eicu,
}


def pares_args():
    parser = argparse.ArgumentParser(description='Build a Dockerfile')
    parser.add_argument("--mimic_iv", type=str, help="MIMIC-IV Path")
    parser.add_argument("--mimic_iv_ed", type=str, help="MIMIC-IV-ED Path")
    parser.add_argument("--mimic_iii", type=str, help="MIMIC-III Path")
    parser.add_argument("--eicu", type=str, help="eicu Path")

    return parser.parse_args()

def add_dataset(data_path, data_name, check_file, ext):
    if os.path.exists(os.path.join(data_path, check_file + '.csv')):
        ext = ""
    elif os.path.exists(os.path.join(data_path, check_file + ".csv.gz")):
        pass
    else:
        raise ValueError(f"Invalid {data_name} Path")
    
    with open(f"{data_name}.sh", 'w') as f:
        f.write(script_dict[data_name].format(ext))
    
    mount_args = ["-v", f"{data_path}:/tmp/{data_name}"]
    write_content = f"COPY {data_name}.sh /docker-entrypoint-initdb.d/{data_name}.sh\n"

    return mount_args, write_content


def main():
    args = pares_args()
    dockerfile = open("Dockerfile", "w")
    dockerfile.write(start)

    run_args = []

    if args.mimic_iv:
        mount_args, write_content = add_dataset(args.mimic_iv, "mimic_iv", "hosp/admissions", "_gz")
        run_args.extend(mount_args)
        dockerfile.write(write_content)
    
    if args.mimic_iv_ed:
        mount_args, write_content = add_dataset(args.mimic_iv_ed, "mimic_iv_ed", "edstays", "_gz")
        run_args.extend(mount_args)
        dockerfile.write(write_content)

    if args.mimic_iii:
        mount_args, write_content = add_dataset(args.mimic_iii, "mimic_iii", "ADMISSIONS", "-gz")
        run_args.extend(mount_args)
        dockerfile.write(write_content)

    if args.eicu:
        mount_args, write_content = add_dataset(args.eicu, "eicu", "patient", "-gz")
        run_args.extend(mount_args)
        dockerfile.write(write_content)

    dockerfile.close()
    print("Dockerfile created")

    # Remove container if exists
    subprocess.run(["docker", "stop", "ehr_postgres"], stderr=subprocess.DEVNULL)
    subprocess.run(["docker", "rm", "ehr_postgres"], stderr=subprocess.DEVNULL)
    subprocess.run(["docker", "image", "rm", "ehr_postgres"], stderr=subprocess.DEVNULL)
    subprocess.run(["docker", "build", "-t", "ehr_postgres", "."])
    subprocess.run(["docker", "run", "--name", "ehr_postgres", "-d", "-p", "5432:5432", "-e", "POSTGRES_PASSWORD=postgres", *run_args, "ehr_postgres"])

    print("Docker container created")

    process = subprocess.Popen(
        ["docker", "logs", "-f", "ehr_postgres"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()

        if "PostgreSQL init process complete" in line:
            print("Initialization complete!")
            process.terminate()
            break

    print("EHR_POSTGRES is ready!")

if __name__ == "__main__":
    main()