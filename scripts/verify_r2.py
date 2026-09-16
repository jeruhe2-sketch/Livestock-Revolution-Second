import subprocess, os, tempfile, json
from PIL import Image

BUCKET = "livestock-library"

def main():
    endpoint = os.environ['R2_ENDPOINT']
    workdir = tempfile.mkdtemp()
    local_dir = os.path.join(workdir, "bucket")

    print("버킷 다운로드 중...", flush=True)
    subprocess.run([
        "aws", "s3", "sync", f"s3://{BUCKET}/", local_dir,
        "--endpoint-url", endpoint, "--profile", "r2"
    ], check=True)

    results = []
    broken = []
    for root, _, files in os.walk(local_dir):
        for fname in files:
            path = os.path.join(root, fname)
            rel = os.path.relpath(path, local_dir)
            ext = fname.lower().rsplit('.', 1)[-1] if '.' in fname else ''
            if ext not in ('jpg', 'jpeg', 'png', 'webp'):
                continue
            size = os.path.getsize(path)
            ok = True
            err = None
            try:
                with Image.open(path) as img:
                    img.verify()
                # verify() 후에는 다시 열어서 실제 로드까지 확인
                with Image.open(path) as img2:
                    img2.load()
            except Exception as e:
                ok = False
                err = str(e)
                broken.append(rel)
            results.append({"key": rel, "size": size, "ok": ok, "error": err})
            status = "OK" if ok else f"손상됨: {err}"
            print(f"{rel} ({size}bytes) - {status}", flush=True)

    with open("verify-result.json", "w") as f:
        json.dump({"total": len(results), "broken": broken, "details": results}, f, ensure_ascii=False, indent=2)

    print(f"\n총 {len(results)}개 중 손상 {len(broken)}개", flush=True)
    if broken:
        print("손상 파일 목록:")
        for b in broken:
            print(" -", b)

if __name__ == "__main__":
    main()
