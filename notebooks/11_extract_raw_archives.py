from pathlib import Path
import zipfile
import gzip
import shutil

ROOT = Path(__file__).resolve().parents[1]

RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"


def extract_zip(path):
    relative = path.relative_to(RAW)
    output_dir = INTERIM / relative.parent / path.stem

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[ZIP] {relative}")

    with zipfile.ZipFile(path, "r") as z:
        z.extractall(output_dir)

    return output_dir


def extract_gzip(path):
    relative = path.relative_to(RAW)

    output_dir = INTERIM / relative.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / path.stem

    print(f"[GZ ] {relative}")

    if output_file.exists():
        return output_file

    with gzip.open(path, "rb") as src:
        with output_file.open("wb") as dst:
            shutil.copyfileobj(src, dst)

    return output_file


def main():

    print("=" * 80)
    print("CHETAKAI V1 RAW ARCHIVE EXTRACTION")
    print("=" * 80)

    zip_files = sorted(RAW.rglob("*.zip"))
    gz_files = sorted(RAW.rglob("*.gz"))

    print(f"ZIP archives : {len(zip_files)}")
    print(f"GZ archives  : {len(gz_files)}")
    print()

    extracted_zip = 0
    extracted_gz = 0

    for path in zip_files:
        try:
            extract_zip(path)
            extracted_zip += 1
        except Exception as e:
            print(f"[ERROR] {path}")
            print(f"        {e}")

    for path in gz_files:
        try:
            extract_gzip(path)
            extracted_gz += 1
        except Exception as e:
            print(f"[ERROR] {path}")
            print(f"        {e}")

    print()
    print("=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"ZIP processed : {extracted_zip}/{len(zip_files)}")
    print(f"GZ processed  : {extracted_gz}/{len(gz_files)}")
    print(f"Output        : {INTERIM}")
    print("=" * 80)


if __name__ == "__main__":
    main()