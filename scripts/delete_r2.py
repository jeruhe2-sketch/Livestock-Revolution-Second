import json, subprocess, os, sys

keys = json.load(open('_pending_delete.json'))
endpoint = os.environ['R2_ENDPOINT']

failed = []
for key in keys:
    print(f"삭제: {key}", flush=True)
    result = subprocess.run([
        "aws", "s3", "rm",
        f"s3://livestock-library/{key}",
        "--endpoint-url", endpoint,
        "--profile", "r2"
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print("  실패:", result.stderr, flush=True)
        failed.append(key)
    else:
        print("  성공", flush=True)

print(f"\n총 {len(keys)}건 중 실패 {len(failed)}건")
if failed:
    print("실패 목록:", failed)
    sys.exit(1)
