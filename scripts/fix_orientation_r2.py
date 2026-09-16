import subprocess, os, sys, tempfile, shutil
from PIL import Image, ImageOps

BUCKET = "livestock-library"
SKIP_PREFIXES = ("thumbs/", "_icons/")

def main():
    endpoint = os.environ['R2_ENDPOINT']
    workdir = tempfile.mkdtemp()
    local_dir = os.path.join(workdir, "bucket")

    print(f"1) 버킷 전체 다운로드 -> {local_dir}", flush=True)
    subprocess.run([
        "aws", "s3", "sync", f"s3://{BUCKET}/", local_dir,
        "--endpoint-url", endpoint, "--profile", "r2"
    ], check=True)

    total = 0
    fixed = 0

    for root, _, files in os.walk(local_dir):
        rel_root = os.path.relpath(root, local_dir).replace(os.sep, "/")
        if rel_root != "." and rel_root.startswith(SKIP_PREFIXES):
            continue
        for fname in files:
            if rel_root != "." and any((rel_root + "/").startswith(p) for p in SKIP_PREFIXES):
                continue
            ext = fname.lower().rsplit('.', 1)[-1] if '.' in fname else ''
            if ext not in ('jpg', 'jpeg', 'png'):
                continue
            path = os.path.join(root, fname)
            total += 1
            try:
                with Image.open(path) as img:
                    exif = img.getexif()
                    orientation = exif.get(0x0112, 1)  # 274 = Orientation tag
                    if orientation and orientation != 1:
                        fixed_img = ImageOps.exif_transpose(img)
                        if fixed_img.mode in ('P',) and ext in ('jpg', 'jpeg'):
                            fixed_img = fixed_img.convert('RGB')
                        fixed_img.save(path)
                        fixed += 1
                        print(f"  회전 보정: {os.path.relpath(path, local_dir)} (orientation={orientation})", flush=True)
            except Exception as e:
                print(f"  !! 실패 {fname}: {e}", flush=True)

    print(f"\n2) 처리 완료: 전체 {total}개 중 EXIF 회전 정보 있던 {fixed}개를 실제 픽셀 회전으로 반영", flush=True)

    if fixed > 0:
        print("3) 보정된 파일 R2에 재업로드", flush=True)
        subprocess.run([
            "aws", "s3", "sync", local_dir, f"s3://{BUCKET}/",
            "--endpoint-url", endpoint, "--profile", "r2"
        ], check=True)
    else:
        print("3) 보정할 파일 없음 (재업로드 생략)", flush=True)

    shutil.rmtree(workdir, ignore_errors=True)
    print("완료", flush=True)

if __name__ == "__main__":
    main()
