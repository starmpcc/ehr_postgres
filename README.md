# ehr_postgres
Postgres Docker container setup scripts for MIMIC-IV (including ED), MIMIC-III, and eICU datasets.

## How-to-use
1. Download EHR data what you want from [physionet](https://physionet.org).
2. Run `python --mimic_iv {MIMIC_IV_PATH} --mimic_iv_ed {MIMIC_IV_ED_PATH} --mimic_iii {MIMIC_III_PATH} --eicu {EICU_PATH}` to bulid and run docker container.
    * NOTE: You can use each option separately.
    * NOTE: This script automatically removes pre-existing containers and images named `ehr_postgres`.
3. Run `PGPASSWORD=postgres psql -h localhost -p 5432 -U postgres`, and enjoy!
    * The database names are `mimiciv`, `mimiciii`, `eicu`.

## NOTE
- This script has been tested with the following dataset versions: MIMC-IV v2.2, MIMIC-IV-ED v2.2, MIMIC-III v1.4, and eICU v2.0.
- The whole process takes few hours.
- Each dataset requires approximately 100GB of storage space.