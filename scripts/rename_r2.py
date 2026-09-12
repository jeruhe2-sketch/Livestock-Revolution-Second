import json, subprocess, os, sys

m = json.load(open('rename-map.json'))
endpoint = os.environ['R2_ENDPOINT']

failed = []
for item in m['renames']:
    src = item['from']
    dst = item['to']
    print(f"이동: {src} -> {dst}", flush=True)
    result = subprocess.run([
        "aws", "s3", "mv",
        f"s3://livestock-library/{src}",
        f"s3://livestock-library/{dst}",
        "--endpoint-url", endpoint,
        "--profile", "r2"
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print("  실패:", result.stderr, flush=True)
        failed.append(src)
    else:
        print("  성공", flush=True)

print(f"\n총 {len(m['renames'])}건 중 실패 {len(failed)}건")
if failed:
    print("실패 목록:", failed)
    sys.exit(1)
